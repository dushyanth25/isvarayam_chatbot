"""LLM orchestration module using Groq API.

Manages tool-calling loops (max 3 rounds), backoff retries for rate limits
(429/5xx), graceful fallback responses, and logging of unanswered queries.
"""

from datetime import datetime, timezone
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from groq import Groq, APIConnectionError, APIStatusError, RateLimitError

from prompts import get_system_prompt
from tools import TOOLS_SCHEMA
from guardrails.tool_guard import execute_guarded_tool
from guardrails.budget import circuit_breaker

logger = logging.getLogger("isvaryam.llm")

DEFAULT_MODEL = "openai/gpt-oss-120b"
MAX_TOOL_ROUNDS = 3
UNMATCHED_LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "unmatched.log")

BUSY_FALLBACK_MESSAGE = (
    "🙏 We're currently experiencing high demand. Please try again in a moment, "
    "or feel free to contact Isvaryam directly via Phone/WhatsApp at +91 9578822000 "
    "or email support@isvaryam.com."
)

MISSING_KEY_MESSAGE = (
    "🌿 Welcome to Isvaryam! The AI service is currently undergoing maintenance. "
    "For immediate inquiries on cold-pressed oils, ghee, or jaggery, please contact us "
    "at +91 9578822000 or visit https://isvaryam.com."
)


def get_model_name() -> str:
    """Get the active Groq model name from env var or default."""
    return os.environ.get("GROQ_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def get_groq_client() -> Optional[Groq]:
    """Initialize Groq client with API key from environment."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        logger.warning("GROQ_API_KEY is not configured.")
        return None
    try:
        return Groq(api_key=api_key)
    except Exception as exc:
        logger.error("Failed to initialize Groq client: %s", exc)
        return None


def log_unmatched_query(user_message: str, reason: str, bot_response: str = "") -> None:
    """Log unanswered or fallback queries for continuous prompt improvement."""
    try:
        os.makedirs(os.path.dirname(UNMATCHED_LOG_PATH), exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        log_entry = (
            f"[{timestamp}] REASON: {reason} | QUERY: {user_message.strip()} | "
            f"RESPONSE: {bot_response.strip()}\n"
        )
        with open(UNMATCHED_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as exc:
        logger.error("Failed to write to unmatched log: %s", exc)


def call_groq_with_retry(
    client: Groq,
    model: str,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[str] = "auto"
) -> Any:
    """Execute a Groq chat completion with one backoff retry on 429 or 5xx."""
    attempts = 0
    max_attempts = 2

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 600,  # Enforce concise output and protect free-tier TPM quota
    }
    if tools:
        kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

    while attempts < max_attempts:
        attempts += 1
        try:
            return client.chat.completions.create(**kwargs)
        except RateLimitError as rle:
            logger.warning("Groq RateLimitError (attempt %d/%d): %s", attempts, max_attempts, rle)
            if attempts < max_attempts:
                time.sleep(2.0)
            else:
                raise
        except APIStatusError as ase:
            # Retry on 5xx server errors
            if ase.status_code >= 500 and attempts < max_attempts:
                logger.warning("Groq 5xx error (attempt %d/%d): %s", attempts, max_attempts, ase)
                time.sleep(1.5)
            else:
                raise
        except APIConnectionError as ace:
            if attempts < max_attempts:
                logger.warning("Groq connection error (attempt %d/%d): %s", attempts, max_attempts, ace)
                time.sleep(1.5)
            else:
                raise


def generate_response(
    user_message: str,
    history: Optional[List[Dict[str, str]]] = None
) -> Tuple[str, List[str]]:
    """Process user query through Groq with a multi-turn tool calling loop.

    Returns:
        Tuple of (response_text, list_of_product_image_urls)
    """
    client = get_groq_client()
    if client is None:
        log_unmatched_query(user_message, "MISSING_GROQ_API_KEY", MISSING_KEY_MESSAGE)
        return MISSING_KEY_MESSAGE, []

    model = get_model_name()
    system_prompt = get_system_prompt()

    # Build messages: system prompt + last 8 turns of history + new user message
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt}
    ]

    if history:
        # History is validated by the caller to contain max 8 turns with valid roles
        for turn in history[-8:]:
            messages.append({
                "role": turn["role"],
                "content": turn["content"]
            })

    messages.append({"role": "user", "content": user_message})

    collected_images: List[str] = []
    unmatched_flag = False

    try:
        # Tool-calling loop up to MAX_TOOL_ROUNDS
        round_idx = 0
        while round_idx < MAX_TOOL_ROUNDS:
            round_idx += 1
            is_last_round = (round_idx == MAX_TOOL_ROUNDS)

            response = call_groq_with_retry(
                client=client,
                model=model,
                messages=messages,
                tools=TOOLS_SCHEMA if not is_last_round else None,
                tool_choice="auto" if not is_last_round else None
            )

            response_message = response.choices[0].message
            tool_calls = getattr(response_message, "tool_calls", None)

            if not tool_calls:
                final_text = response_message.content or ""
                # Check if model expressed uncertainty or missing data
                lower_final = final_text.lower()
                if any(phrase in lower_final for phrase in ["not found", "don't have information", "unable to find"]):
                    unmatched_flag = True

                if unmatched_flag:
                    log_unmatched_query(user_message, "UNMATCHED_PRODUCT_OR_INFO", final_text)

                return final_text, collected_images

            # Process tool calls
            # Append assistant's turn with tool_calls
            messages.append(response_message)

            for tc in tool_calls:
                call_id = tc.id
                func_name = tc.function.name
                raw_args = tc.function.arguments
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except Exception:
                    args = {}

                logger.info("Executing tool: %s with args: %s", func_name, args)
                tool_output_str = execute_guarded_tool(func_name, args)

                # Extract images and detect if tool reported not found
                try:
                    raw_json_str = tool_output_str
                    if "<tool_data>" in tool_output_str and "</tool_data>" in tool_output_str:
                        raw_json_str = tool_output_str.split("<tool_data>")[1].split("</tool_data>")[0].strip()
                    tool_data = json.loads(raw_json_str)
                    if isinstance(tool_data, dict):
                        if tool_data.get("found") is False:
                            unmatched_flag = True
                        imgs = tool_data.get("images", [])
                        for img in imgs:
                            if isinstance(img, str) and img.startswith("https://") and img not in collected_images:
                                collected_images.append(img)
                except Exception:
                    pass

                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": func_name,
                    "content": tool_output_str
                })

        # Final forced completion after tool iterations
        final_response = call_groq_with_retry(
            client=client,
            model=model,
            messages=messages,
            tools=None
        )
        final_text = final_response.choices[0].message.content or ""
        if unmatched_flag:
            log_unmatched_query(user_message, "UNMATCHED_TOOL_QUERY", final_text)

        circuit_breaker.record_success()
        return final_text, collected_images

    except RateLimitError as rle:
        circuit_breaker.record_failure()
        logger.error("Rate limit exhausted on Groq: %s", rle)
        log_unmatched_query(user_message, "RATE_LIMIT_429", BUSY_FALLBACK_MESSAGE)
        return BUSY_FALLBACK_MESSAGE, []
    except (APIStatusError, APIConnectionError) as apierr:
        circuit_breaker.record_failure()
        logger.error("Groq API error: %s", apierr)
        log_unmatched_query(user_message, f"API_ERROR_{getattr(apierr, 'status_code', 'CONN')}", BUSY_FALLBACK_MESSAGE)
        return BUSY_FALLBACK_MESSAGE, []
    except Exception as exc:
        logger.error("Unexpected error in LLM generation: %s", exc, exc_info=True)
        log_unmatched_query(user_message, "EXCEPTION", BUSY_FALLBACK_MESSAGE)
        return BUSY_FALLBACK_MESSAGE, []
