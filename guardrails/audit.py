"""Audit Logging Guardrail.

Records blocked events, policy violations, and fallback triggers into a
JSON-lines log file (logs/guardrail_audit.jsonl). Never logs raw IP addresses,
secrets, or sensitive user data.
"""

from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, Optional
from guardrails.abuse import hash_identifier

logger = logging.getLogger("isvaryam.guardrails.audit")

AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "guardrail_audit.jsonl")


def record_audit_event(
    reason: str,
    raw_ip: str,
    session_id: Optional[str],
    raw_message: str,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Write an audit entry in JSONL format."""
    try:
        os.makedirs(os.path.dirname(AUDIT_LOG_FILE), exist_ok=True)

        hashed_ip = hash_identifier(raw_ip)
        hashed_session = hash_identifier(session_id) if session_id else "anonymous"

        # Truncate message to max 100 chars, stripping newlines
        clean_msg = str(raw_message or "").replace("\n", " ").strip()
        truncated_msg = clean_msg[:100]

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "hashed_ip": hashed_ip,
            "hashed_session": hashed_session,
            "truncated_message": truncated_msg,
            "metadata": metadata or {}
        }

        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    except Exception as exc:
        logger.error("Failed to write to guardrail audit log: %s", exc)

