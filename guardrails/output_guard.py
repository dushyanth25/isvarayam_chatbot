"""Output Guardrail for Isvaryam Chatbot.

Enforces:
1. Extraction and verification of all Rs/INR amounts against verified catalog/tool data.
2. Strict domain, phone, and email allowlist.
3. Canary-string leak detection (detects system prompt exfiltration).
4. Medical claim keyword detection (prevents false disease cure/treatment claims).
5. Output length caps.
6. Returns safe fallback message and reason code on failure.
"""

import logging
import re
import secrets
from typing import List, Optional, Set, Tuple

logger = logging.getLogger("isvaryam.guardrails.output")

# Generate secure random canary string at runtime startup
CANARY_TOKEN = f"CANARY_SECRET_{secrets.token_hex(12)}"

# Static baseline catalog prices in INR (sizes, standard prices)
BASELINE_ALLOWED_PRICES: Set[int] = {
    65, 120, 160, 185, 220, 250, 310, 350, 360, 400, 430, 500, 680, 1050, 1500
}

# Allowlist for domains, phones, emails
ALLOWED_DOMAINS = {"isvaryam.com", "cdnjs.cloudflare.com"}
ALLOWED_PHONES = {"9578822000", "+919578822000", "+91 9578822000"}
ALLOWED_EMAILS = {"support@isvaryam.com"}

# Medical claim detection patterns
MEDICAL_CLAIM_PATTERNS = [
    r'\bcure[s]?\s+(?:cancer|diabetes|arthritis|heart\s+disease|blood\s+pressure|asthma|covid|paralysis)\b',
    r'\btreat[s]?\s+(?:cancer|diabetes|arthritis|hypertension|blood\s+pressure)\b',
    r'\bheals?\s+(?:diabetes|cancer|chronic\s+disease|arthritis|heart\s+disease|hypertension)\b',
    r'\breplaces?\s+(?:your\s+)?(?:prescription|medicine|doctor)\b',
    r'\bmedical\s+cure\b',
    r'\bprescribe\s+(?:medicine|dosage)\b',
    r'மருத்துவ\s+சிகிச்சை',
    r'நோயை\s+குணப்படுத்தும்',
]
RE_MEDICAL_CLAIMS = [re.compile(p, re.IGNORECASE) for p in MEDICAL_CLAIM_PATTERNS]

# Regex for price extraction: e.g. ₹310, Rs. 430, Rs 160, 1050 INR, INR 360
RE_PRICES = re.compile(r'(?:₹|Rs\.?|INR)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:₹|Rs\.?|INR)', re.IGNORECASE)

# URL / Domain extraction
RE_URLS = re.compile(r'https?://([A-Za-z0-9\.\-_]+)(?:[:/][^\s]*)?', re.IGNORECASE)
RE_PHONES = re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
RE_EMAILS = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

MAX_OUTPUT_LENGTH = 1500

SAFE_FALLBACK_RESPONSE = (
    "🌿 Vanakkam! For verified product pricing, health details, and order assistance, "
    "please visit our official store at https://isvaryam.com or reach Isvaryam in "
    "Coimbatore directly at +91 9578822000 or support@isvaryam.com."
)


def get_system_canary() -> str:
    """Return the active runtime canary token for inclusion in the system prompt."""
    return CANARY_TOKEN


def extract_prices_from_text(text: str) -> List[float]:
    """Extract all mentioned rupee figures from text."""
    prices: List[float] = []
    matches = RE_PRICES.findall(text)
    for m in matches:
        val_str = m[0] or m[1]
        try:
            val = float(val_str)
            prices.append(val)
        except ValueError:
            pass
    return prices


def validate_output(
    output_text: str,
    allowed_prices_extra: Optional[Set[int]] = None
) -> Tuple[bool, str, str]:
    """Verify generated LLM text against price hallucination, canary leak, and medical claims.

    Returns:
        (allowed: bool, reason_code: str, output_or_fallback: str)
    """
    if not isinstance(output_text, str) or not output_text.strip():
        return False, "EMPTY_OUTPUT", SAFE_FALLBACK_RESPONSE

    # 1. Length cap check
    if len(output_text) > MAX_OUTPUT_LENGTH:
        logger.warning("Output guard: length cap exceeded (%d chars)", len(output_text))
        return False, "OUTPUT_TOO_LONG", SAFE_FALLBACK_RESPONSE

    # 2. Canary leak check (detects prompt exfiltration)
    if CANARY_TOKEN in output_text:
        logger.error("Output guard: canary leak detected!")
        return False, "CANARY_LEAK", SAFE_FALLBACK_RESPONSE

    # 3. Medical claims check
    for pattern in RE_MEDICAL_CLAIMS:
        if pattern.search(output_text):
            logger.warning("Output guard: medical claim detected in output")
            return False, "MEDICAL_CLAIM", SAFE_FALLBACK_RESPONSE

    # 4. Price & currency amount verification
    valid_prices = set(BASELINE_ALLOWED_PRICES)
    if allowed_prices_extra:
        valid_prices.update(allowed_prices_extra)

    mentioned_prices = extract_prices_from_text(output_text)
    for p in mentioned_prices:
        int_p = int(round(p))
        if int_p not in valid_prices:
            logger.warning("Output guard: unverified price Rs. %s mentioned", p)
            return False, "UNVERIFIED_PRICE", SAFE_FALLBACK_RESPONSE

    # 5. Domain allowlist check
    for match in RE_URLS.finditer(output_text):
        domain = match.group(1).lower()
        if domain not in ALLOWED_DOMAINS and not domain.endswith(".isvaryam.com"):
            logger.warning("Output guard: unauthorized domain '%s'", domain)
            return False, "UNAUTHORIZED_DOMAIN", SAFE_FALLBACK_RESPONSE

    # 6. Email allowlist check
    for match in RE_EMAILS.finditer(output_text):
        email = match.group(0).lower()
        if email not in ALLOWED_EMAILS:
            logger.warning("Output guard: unauthorized email '%s'", email)
            return False, "UNAUTHORIZED_EMAIL", SAFE_FALLBACK_RESPONSE

    # 7. Phone allowlist check
    for match in RE_PHONES.finditer(output_text):
        phone_raw = match.group(0).replace(" ", "").replace("-", "")
        clean_phone = phone_raw[-10:]  # last 10 digits
        if clean_phone != "9578822000":
            logger.warning("Output guard: unauthorized phone '%s'", phone_raw)
            return False, "UNAUTHORIZED_PHONE", SAFE_FALLBACK_RESPONSE

    return True, "ALLOWED", output_text

