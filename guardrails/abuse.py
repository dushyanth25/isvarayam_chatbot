"""Abuse and Strike Tracking Guardrail.

Maintains in-memory strike records per hashed session/IP.
3 strikes result in an automatic 1-hour block (3600 seconds).
"""

import hashlib
import os
import time
from typing import Dict, Tuple

BLOCK_DURATION_SECONDS = 3600.0  # 1 hour
MAX_STRIKES = 3

# Salt for hashing identifiers (generated or read from env)
HASH_SALT = os.environ.get("GUARDRAIL_SALT", "isvaryam_salt_cbe_2026").encode("utf-8")


def hash_identifier(identifier: str) -> str:
    """Create a non-reversible SHA-256 hash of IP or session ID."""
    clean = (identifier or "unknown").strip().encode("utf-8")
    return hashlib.sha256(clean + HASH_SALT).hexdigest()[:16]


class AbuseTracker:
    """In-memory strike counter with time-based block expiration."""

    def __init__(self, max_strikes: int = MAX_STRIKES, block_duration: float = BLOCK_DURATION_SECONDS):
        self.max_strikes = max_strikes
        self.block_duration = block_duration
        self._records: Dict[str, Dict[str, float]] = {}

    def is_blocked(self, identifier: str) -> Tuple[bool, float]:
        """Check if identifier is blocked.

        Returns:
            (is_blocked: bool, remaining_seconds: float)
        """
        h_id = hash_identifier(identifier)
        record = self._records.get(h_id)
        if not record:
            return False, 0.0

        blocked_until = record.get("blocked_until", 0.0)
        now = time.time()

        if now < blocked_until:
            return True, round(blocked_until - now, 1)

        # Block has expired
        if blocked_until > 0.0:
            self._records.pop(h_id, None)

        return False, 0.0

    def record_strike(self, identifier: str, reason: str = "") -> Tuple[bool, int, float]:
        """Record an infraction strike.

        Returns:
            (is_now_blocked: bool, remaining_strikes: int, blocked_seconds: float)
        """
        h_id = hash_identifier(identifier)
        now = time.time()
        record = self._records.setdefault(h_id, {
            "strikes": 0,
            "blocked_until": 0.0,
            "last_strike": now
        })

        # If already blocked, maintain block
        if now < record["blocked_until"]:
            return True, 0, round(record["blocked_until"] - now, 1)

        record["strikes"] += 1
        record["last_strike"] = now

        if record["strikes"] >= self.max_strikes:
            record["blocked_until"] = now + self.block_duration
            return True, 0, self.block_duration

        remaining = self.max_strikes - int(record["strikes"])
        return False, remaining, 0.0

    def reset(self, identifier: str = None):
        """Reset strikes for an identifier or all records."""
        if identifier:
            self._records.pop(hash_identifier(identifier), None)
        else:
            self._records.clear()


# Global abuse tracker instance
abuse_tracker = AbuseTracker()

