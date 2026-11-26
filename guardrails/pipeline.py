"""Central Guardrail Pipeline.

Chains the security and reliability layers:
edge -> abuse_check -> budget_check -> input_guard -> history_guard -> LLM (tools via tool_guard) -> output_guard.

Fail closed: Any guard failure or unhandled exception returns a safe fallback message.
"""

from dataclasses import dataclass
import logging
from typing import Any, List, Optional

from guardrails.abuse import abuse_tracker
from guardrails.audit import record_audit_event
from guardrails.budget import check_budget_and_breaker, budget_tracker
from guardrails.history_guard import validate_and_sanitize_history
from guardrails.input_guard import validate_input
from guardrails.output_guard import validate_output, SAFE_FALLBACK_RESPONSE

logger = logging.getLogger("isvaryam.guardrails.pipeline")


@dataclass
class GuardrailResult:
    allowed: bool
    status_code: int
    response_text: str
    images: List[str]
    reason_code: str


def execute_guardrail_pipeline(
    raw_message: str,
    raw_history: Any,
    client_ip: str,
    session_id: Optional[str] = None,
    llm_caller=None
) -> GuardrailResult:
    """Execute end-to-end guardrail pipeline with fail-closed guarantee."""
    effective_session = session_id or client_ip

    try:
        # 1. Abuse & Block Check
        is_blocked, remaining_sec = abuse_tracker.is_blocked(effective_session)
        if is_blocked:
            record_audit_event("ABUSE_BLOCKED", client_ip, effective_session, raw_message, {"remaining_sec": remaining_sec})
            return GuardrailResult(
                allowed=False,
                status_code=429,
                response_text=f"⚠️ Too many policy infractions. You are temporarily blocked. Please retry in {int(remaining_sec)} seconds.",
                images=[],
                reason_code="ABUSE_BLOCKED"
            )

        # 2. Budget, Kill Switch & Circuit Breaker Check
        budget_ok, budget_reason, budget_fallback = check_budget_and_breaker(effective_session)
        if not budget_ok:
            record_audit_event(budget_reason, client_ip, effective_session, raw_message)
            return GuardrailResult(
                allowed=False,
                status_code=200 if budget_reason == "KILL_SWITCH_ACTIVE" else 429,
                response_text=budget_fallback,
                images=[],
                reason_code=budget_reason
            )

        # 3. Input Guard (normalization, length caps, injections, blobs)
        input_ok, input_reason, sanitized_message = validate_input(raw_message)
        if not input_ok:
            # Record abuse strike on malicious inputs (injections, floods, blobs)
            is_now_blocked, remaining_strikes, block_sec = abuse_tracker.record_strike(effective_session, input_reason)
            record_audit_event(
                input_reason, client_ip, effective_session, raw_message,
                {"remaining_strikes": remaining_strikes, "blocked": is_now_blocked}
            )

            if input_reason == "INVALID_TYPE":
                return GuardrailResult(
                    allowed=False, status_code=400,
                    response_text="Field 'message' is required and must be a string",
                    images=[], reason_code=input_reason
                )
            elif input_reason == "EMPTY_INPUT":
                return GuardrailResult(
                    allowed=False, status_code=400,
                    response_text="Field 'message' is required and cannot be blank",
                    images=[], reason_code=input_reason
                )
            elif input_reason == "LENGTH_EXCEEDED":
                return GuardrailResult(
                    allowed=False, status_code=400,
                    response_text="Message exceeds the maximum limit of 500 characters",
                    images=[], reason_code=input_reason
                )
            else:
                # Injection, blob, or flood refusal
                refusal_msg = (
                    "I am the Isvaryam Assistant for cold-pressed oils and natural products. "
                    "I cannot process that request. How may I help you with our oils, ghee, or jaggery?"
                )
                return GuardrailResult(
                    allowed=False, status_code=200,
                    response_text=refusal_msg,
                    images=[], reason_code=input_reason
                )

        # 4. History Guard
        history_ok, history_reason, sanitized_history = validate_and_sanitize_history(raw_history)
        if not history_ok:
            abuse_tracker.record_strike(effective_session, history_reason)
            record_audit_event(history_reason, client_ip, effective_session, raw_message)
            return GuardrailResult(
                allowed=False, status_code=400,
                response_text=history_reason,
                images=[], reason_code="INVALID_HISTORY"
            )

        # 5. LLM Call with Tool Guard
        if llm_caller is None:
            import llm
            llm_caller = llm.generate_response

        raw_llm_text, images = llm_caller(
            user_message=sanitized_message,
            history=sanitized_history
        )

        # Track token consumption (estimated ~ 1 token per 4 characters)
        estimated_tokens = (len(sanitized_message) + len(raw_llm_text)) // 4
        budget_tracker.record_tokens(estimated_tokens)

        # 6. Output Guard
        output_ok, output_reason, final_text = validate_output(raw_llm_text)
        if not output_ok:
            record_audit_event(output_reason, client_ip, effective_session, raw_message, {"raw_output": raw_llm_text[:100]})
            return GuardrailResult(
                allowed=True,  # Client receives safe fallback with 200
                status_code=200,
                response_text=final_text,
                images=[],
                reason_code=output_reason
            )

        return GuardrailResult(
            allowed=True,
            status_code=200,
            response_text=final_text,
            images=images,
            reason_code="ALLOWED"
        )

    except Exception as exc:
        logger.error("Unhandled exception in guardrail pipeline: %s", exc, exc_info=True)
        record_audit_event("PIPELINE_EXCEPTION", client_ip, effective_session, raw_message, {"error": str(exc)})
        return GuardrailResult(
            allowed=False,
            status_code=500,
            response_text=SAFE_FALLBACK_RESPONSE,
            images=[],
            reason_code="FAIL_CLOSED_EXCEPTION"
        )
