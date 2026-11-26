"""History Guardrail for Isvaryam Chatbot.

Enforces role restrictions (only 'user' and 'assistant'), limits conversation
depth to a safe maximum, strips injected metadata fields, and enforces
per-turn character ceilings.
"""

from typing import Any, Dict, List, Tuple
from guardrails.input_guard import normalize_text

ALLOWED_ROLES = {"user", "assistant"}
DEFAULT_MAX_TURNS = 8
DEFAULT_MAX_TURN_LENGTH = 1000


def validate_and_sanitize_history(
    raw_history: Any,
    max_turns: int = DEFAULT_MAX_TURNS,
    max_turn_length: int = DEFAULT_MAX_TURN_LENGTH
) -> Tuple[bool, str, List[Dict[str, str]]]:
    """Validate and sanitize multi-turn conversation history.

    Returns:
        (allowed: bool, reason_code: str, sanitized_history: List[Dict[str, str]])
    """
    if raw_history is None:
        return True, "ALLOWED", []

    if not isinstance(raw_history, list):
        return False, "HISTORY_NOT_LIST: Field 'history' must be a list", []

    if len(raw_history) > max_turns:
        return False, f"HISTORY_TOO_LONG: Field 'history' can contain at most {max_turns} items", []

    sanitized: List[Dict[str, str]] = []

    for idx, item in enumerate(raw_history):
        if not isinstance(item, dict):
            return False, f"HISTORY_ITEM_NOT_DICT: History item {idx} must be an object", []

        role = item.get("role")
        if role not in ALLOWED_ROLES:
            return False, f"DISALLOWED_ROLE: History item {idx} has invalid role '{role}'. Only 'user' or 'assistant' permitted.", []

        content = item.get("content")
        if not isinstance(content, str):
            return False, f"NON_STRING_CONTENT: History item {idx} content must be a string", []

        if len(content) > max_turn_length:
            return False, f"CONTENT_LENGTH_EXCEEDED: History item {idx} exceeds {max_turn_length} character limit", []

        normalized_content = normalize_text(content)
        sanitized.append({
            "role": role,
            "content": normalized_content
        })

    return True, "ALLOWED", sanitized
