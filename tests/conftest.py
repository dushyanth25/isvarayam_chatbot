"""Pytest fixtures and configuration."""

import pytest
from app import limiter
from guardrails.abuse import abuse_tracker
from guardrails.budget import budget_tracker, circuit_breaker


@pytest.fixture(autouse=True)
def clean_rate_limit_and_guards():
    """Reset rate limiter buckets and in-memory guardrail trackers before each test."""
    try:
        limiter.reset()
        abuse_tracker.reset()
        circuit_breaker.reset()
        budget_tracker.reset()
    except Exception:
        pass
    yield
    try:
        limiter.reset()
        abuse_tracker.reset()
        circuit_breaker.reset()
        budget_tracker.reset()
    except Exception:
        pass
