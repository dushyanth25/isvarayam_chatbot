"""Flask Application for Isvaryam Customer Support Chatbot.

Provides endpoints for the web UI, health checking, and rate-limited
LLM chatbot interactions with comprehensive validation and security headers.
"""

from datetime import datetime, timezone
import logging
import os
import re

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, Response
from werkzeug.exceptions import HTTPException
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import db
import llm
from guardrails.pipeline import execute_guardrail_pipeline

# Load environment variables from .env if present
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s in %(name)s: %(message)s"
)
logger = logging.getLogger("isvaryam.app")

app = Flask(
    __name__,
    static_url_path='/static',
    static_folder='static',
    template_folder='templates'
)

# Max request payload size: 32 KB (protects against oversized payload DoS)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024

# Per-IP Rate Limiting: 10 requests/min, 200 requests/day
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "10 per minute"],
    storage_uri="memory://"
)


@app.errorhandler(413)
def request_entity_too_large_handler(e):
    """Handle oversized payloads with clean JSON."""
    return jsonify({
        "error": "Payload too large. Maximum allowed size is 32 KB.",
        "status": 413
    }), 413


@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit exhaustion with clean JSON."""
    return jsonify({
        "error": "Rate limit exceeded. Please wait a moment before sending more messages.",
        "status": 429
    }), 429


@app.errorhandler(500)
def internal_error_handler(e):
    """Ensure internal errors never leak stack traces to the client."""
    logger.error("Internal Server Error: %s", e, exc_info=True)
    return jsonify({
        "error": "An unexpected error occurred. Please try again or contact Isvaryam at +91 9578822000.",
        "status": 500
    }), 500


_ORIGIN_PATTERN = re.compile(r"^https?://[a-zA-Z0-9.-]+(?::\d+)?$")
DEFAULT_FRAME_ORIGINS = "https://www.isvaryam.com"


def _get_allowed_frame_origins() -> list[str]:
    """Parse and validate ALLOWED_FRAME_ORIGINS env var (rejects wildcards)."""
    raw = os.environ.get("ALLOWED_FRAME_ORIGINS", DEFAULT_FRAME_ORIGINS)
    valid_origins: list[str] = []
    for token in re.split(r"[\s,]+", raw.strip()):
        origin = token.rstrip("/")
        if not origin or origin == "'self'" or "*" in origin:
            continue
        if _ORIGIN_PATTERN.match(origin) and origin not in valid_origins:
            valid_origins.append(origin)
    return valid_origins


@app.after_request
def set_security_headers(response: Response) -> Response:
    """Enforce standard security headers and secure CSP."""
    allowed_origins = _get_allowed_frame_origins()
    frame_ancestors = "'self'" if not allowed_origins else f"'self' {' '.join(allowed_origins)}"

    response.headers["X-Content-Type-Options"] = "nosniff"
    if allowed_origins:
        # Omit X-Frame-Options when cross-origin frame-ancestors are explicitly allowed
        # so legacy SAMEORIGIN does not conflict with CSP frame-ancestors.
        response.headers.pop("X-Frame-Options", None)
    else:
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Strict CSP: no 'unsafe-inline' for script-src since chat.js is external
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "img-src 'self' data: https:; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "connect-src 'self'; "
        f"frame-ancestors {frame_ancestors}; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    return response


@app.route("/")
def index():
    """Render main chat interface."""
    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health():
    """Service health inspection endpoint."""
    is_connected = db.is_db_connected()
    model_name = llm.get_model_name()
    has_groq_key = bool(os.environ.get("GROQ_API_KEY", "").strip())

    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "connected" if is_connected else "disconnected (fallback active)",
        "model": model_name,
        "llm_ready": has_groq_key
    }), 200


@app.route("/chatbot", methods=["POST"])
@limiter.limit("10 per minute")
def chatbot():
    """Process customer message through full guardrail pipeline and LLM agent."""
    try:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Payload must be a JSON object", "status": 400}), 400

        raw_message = payload.get("message")
        raw_history = payload.get("history")

        client_ip = get_remote_address()
        session_id = request.headers.get("X-Session-ID") or client_ip

        # Execute centralized security and reliability guardrail pipeline
        result = execute_guardrail_pipeline(
            raw_message=raw_message,
            raw_history=raw_history,
            client_ip=client_ip,
            session_id=session_id
        )

        if result.status_code == 400:
            return jsonify({"error": result.response_text, "status": 400, "reason": result.reason_code}), 400
        elif result.status_code == 429:
            return jsonify({"error": result.response_text, "status": 429, "reason": result.reason_code}), 429

        return jsonify({
            "response": result.response_text,
            "images": result.images,
            "status": result.status_code,
            "reason": result.reason_code
        }), result.status_code

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unhandled exception in /chatbot endpoint: %s", exc, exc_info=True)
        return jsonify({
            "response": "⚠️ Sorry, something went wrong. Please try again or reach out to us at +91 9578822000.",
            "images": [],
            "status": 500
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
