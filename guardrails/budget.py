"""Token and Budget Guardrail with Circuit Breaker and Kill Switch.

Features:
1. Daily token budget tracker with automatic UTC date roll-over.
2. Per-session request volume counter.
3. Circuit breaker tripping after 5 consecutive Groq failures (60s open window).
4. Kill switch via LLM_ENABLED environment variable returning canned replies.
"""

from datetime import datetime, timezone
import logging
import os
import time
from typing import Dict, Tuple

logger = logging.getLogger("isvaryam.guardrails.budget")

# Circuit breaker thresholds
CIRCUIT_FAILURE_THRESHOLD = 5
CIRCUIT_OPEN_DURATION_SECONDS = 60.0

# Budget defaults
DEFAULT_DAILY_TOKEN_BUDGET = int(os.environ.get("DAILY_TOKEN_BUDGET", "500000"))
DEFAULT_SESSION_REQUEST_LIMIT = int(os.environ.get("SESSION_REQUEST_LIMIT", "50"))

CANNED_KILL_SWITCH_RESPONSE = (
    "🌿 Vanakkam! Our automated AI assistant is currently paused for scheduled maintenance. "
    "To view products or place orders, please visit our online store at https://isvaryam.com "
    "or contact our Coimbatore team directly at +91 9578822000."
)

CANNED_CIRCUIT_OPEN_RESPONSE = (
    "🙏 We are experiencing temporary connectivity delays with our AI service. "
    "Please try again in a minute, or reach Isvaryam directly via Phone/WhatsApp at "
    "+91 9578822000."
)

CANNED_BUDGET_EXCEEDED_RESPONSE = (
    "🌿 We have reached our daily automated assistant limit. "
    "For immediate inquiries on oils, ghee, or jaggery, please visit https://isvaryam.com "
    "or call us at +91 9578822000."
)


class CircuitBreaker:
    """In-memory 3-state circuit breaker: CLOSED, OPEN, HALF_OPEN."""

    def __init__(
        self,
        failure_threshold: int = CIRCUIT_FAILURE_THRESHOLD,
        open_duration: float = CIRCUIT_OPEN_DURATION_SECONDS
    ):
        self.failure_threshold = failure_threshold
        self.open_duration = open_duration
        self.consecutive_failures = 0
        self.state = "CLOSED"
        self.opened_at = 0.0

    def record_success(self):
        """Reset failure counter on successful upstream response."""
        self.consecutive_failures = 0
        self.state = "CLOSED"

    def record_failure(self):
        """Track failures and open circuit if threshold exceeded."""
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.state = "OPEN"
            self.opened_at = time.time()
            logger.warning(
                "Circuit breaker tripped to OPEN after %d consecutive failures.",
                self.consecutive_failures
            )

    def allow_request(self) -> bool:
        """Determine if request is permitted through the circuit."""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            if time.time() - self.opened_at >= self.open_duration:
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker transitioned from OPEN to HALF_OPEN (probe allowed).")
                return True
            return False

        # HALF_OPEN allows probe
        return True

    def reset(self):
        """Reset circuit breaker to initial closed state."""
        self.consecutive_failures = 0
        self.state = "CLOSED"
        self.opened_at = 0.0


class BudgetTracker:
    """Tracks daily token consumption and per-session request velocity."""

    def __init__(
        self,
        daily_token_budget: int = DEFAULT_DAILY_TOKEN_BUDGET,
        session_request_limit: int = DEFAULT_SESSION_REQUEST_LIMIT
    ):
        self.daily_token_budget = daily_token_budget
        self.session_request_limit = session_request_limit
        self.current_day_str = self._get_current_day()
        self.tokens_consumed_today = 0
        self.session_counts: Dict[str, int] = {}

    def _get_current_day(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _check_and_reset_daily(self):
        today = self._get_current_day()
        if today != self.current_day_str:
            self.current_day_str = today
            self.tokens_consumed_today = 0
            self.session_counts.clear()

    def record_tokens(self, tokens: int):
        self._check_and_reset_daily()
        self.tokens_consumed_today += max(tokens, 0)

    def is_token_budget_exceeded(self) -> bool:
        self._check_and_reset_daily()
        return self.tokens_consumed_today >= self.daily_token_budget

    def record_session_request(self, session_id: str) -> bool:
        """Increment request count for session; returns False if exceeded."""
        self._check_and_reset_daily()
        current = self.session_counts.get(session_id, 0) + 1
        self.session_counts[session_id] = current
        return current <= self.session_request_limit

    def reset(self):
        """Reset all budget counters."""
        self.tokens_consumed_today = 0
        self.session_counts.clear()
        self.current_day_str = self._get_current_day()


# Global Singleton instances
circuit_breaker = CircuitBreaker()
budget_tracker = BudgetTracker()


def is_llm_enabled() -> bool:
    """Inspect environment kill-switch LLM_ENABLED."""
    val = os.environ.get("LLM_ENABLED", "true").strip().lower()
    return val not in ("false", "0", "no", "disabled", "off")


def check_budget_and_breaker(session_id: str) -> Tuple[bool, str, str]:
    """Verify kill switch, budget limits, and circuit breaker health.

    Returns:
        (allowed: bool, reason_code: str, fallback_message: str)
    """
    if not is_llm_enabled():
        return False, "KILL_SWITCH_ACTIVE", CANNED_KILL_SWITCH_RESPONSE

    if not circuit_breaker.allow_request():
        return False, "CIRCUIT_BREAKER_OPEN", CANNED_CIRCUIT_OPEN_RESPONSE

    if budget_tracker.is_token_budget_exceeded():
        return False, "TOKEN_BUDGET_EXCEEDED", CANNED_BUDGET_EXCEEDED_RESPONSE

    if not budget_tracker.record_session_request(session_id):
        return False, "SESSION_LIMIT_EXCEEDED", CANNED_BUDGET_EXCEEDED_RESPONSE

    return True, "ALLOWED", ""

