"""Input Guardrail for Isvaryam Chatbot.

Normalizes incoming text (NFKC, zero-width/control character removal),
enforces strict length limits, detects repeated-character floods, rejects
base64/hex payloads, and detects prompt injection across English, Tamil script,
and Tanglish.
"""

import re
import unicodedata
from typing import Tuple

# Disallowed zero-width and directional control characters
ZERO_WIDTH_CHARS = {
    '\u200b',  # Zero width space
    '\u200c',  # Zero width non-joiner
    '\u200d',  # Zero width joiner
    '\ufeff',  # Zero width no-break space / BOM
    '\u200e',  # Left-to-right mark
    '\u200f',  # Right-to-left mark
    '\u202a',  # LRE
    '\u202b',  # RLE
    '\u202c',  # PDF
    '\u202d',  # LRO
    '\u202e',  # RLO
}

# Regex patterns for payloads
RE_REPEATED_CHARS = re.compile(r'(.)\1{14,}')
def is_base64_blob(s: str) -> bool:
    """Detect contiguous or padded Base64 payloads of 30+ characters."""
    for token in re.split(r'[\s,;:?]+', s):
        clean_token = token.rstrip("=")
        if len(clean_token) >= 30 and re.fullmatch(r'[A-Za-z0-9+/]+', clean_token):
            return True
    return False


def is_hex_blob(s: str) -> bool:
    """Detect contiguous or space-separated hex blobs of 30+ hex digits."""
    # Contiguous hex blob
    if re.search(r'(?:^|[\s,;:?])(?:0x)?([0-9a-fA-F]{30,})(?:$|[\s,;:?])', s):
        return True
    # Space-separated sequence of hex words
    words = s.split()
    hex_digits = sum(len(w) for w in words if re.fullmatch(r'[0-9a-fA-F]+', w))
    if hex_digits >= 30 and len(words) >= 3:
        return True
    return False

# Multi-lingual prompt injection signatures
INJECTION_PATTERNS_EN = [
    r'ignore\s+(?:all\s+|previous\s+)?instructions',
    r'disregard\s+(?:all\s+|previous\s+)?(?:rules|instructions)',
    r'system\s+prompt',
    r'(?:you\s+are\s+now|act\s+as)\s+dan\b',
    r'jailbreak',
    r'developer\s+mode',
    r'override\s+(?:all\s+)?rules',
    r'forget\s+(?:your\s+)?instructions',
    r'(?:reveal|print|show)\s+(?:your\s+)?(?:system\s+)?prompt',
    r'show\s+your\s+instructions',
    r'repeat\s+the\s+text\s+above',
    r'output\s+initialization\s+prompt',
    r'bypass\s+(?:content\s+)?filter',
]

INJECTION_PATTERNS_TANGLISH = [
    r'rule[s]?[-_]?[a|ai]?\s+m[a|aa]thu',
    r'rules[-_]?a\s+ignore\s+pannu',
    r'system\s+prompt[-_]?a\s+(?:print|kaatu|sol)\b',
    r'prompt[-_]?a\s+(?:kudu|sol)\b',
    r'munnadi\s+sonna\s+rules[-_]?a\s+maran?th?udu',
    r'un[n]?oda\s+instructions\s+sol',
    r'developer\s+mode\s+activate\s+pannu',
    r'un\s+rules[-_]?a\s+override\s+pannu',
]

INJECTION_PATTERNS_TAMIL = [
    r'விதிமுறைகளை\s+புறக்கணி',
    r'முந்தைய\s+வழிமுறைகளை\s+புறக்கணி',
    r'சிஸ்டம்\s+பிராம்ப்ட்',
    r'உன்\s+விதிமுறைகளை\s+காட்டு',
    r'வழிமுறைகளை\s+வெளிப்படுத்து',
    r'விதியை\s+மாற்று',
]

ALL_INJECTION_REGEX = [
    re.compile(p, re.IGNORECASE) for p in (
        INJECTION_PATTERNS_EN + INJECTION_PATTERNS_TANGLISH + INJECTION_PATTERNS_TAMIL
    )
]


def normalize_text(text: str) -> str:
    """Normalize unicode to NFKC and strip zero-width and non-whitespace control characters."""
    if not isinstance(text, str):
        return ""

    # NFKC normalisation expands ligatures and canonicalizes glyphs
    normalized = unicodedata.normalize("NFKC", text)

    # Strip zero-width formatting characters
    cleaned_chars = []
    for char in normalized:
        if char in ZERO_WIDTH_CHARS:
            continue
        cat = unicodedata.category(char)
        # Disallow control characters (Cc) and format characters (Cf) except basic spacing
        if cat in ('Cc', 'Cf') and char not in ('\t', '\n', '\r', ' '):
            continue
        cleaned_chars.append(char)

    return "".join(cleaned_chars).strip()


def validate_input(raw_text: str, max_length: int = 500) -> Tuple[bool, str, str]:
    """Validate user input against length, injection, and blob constraints.

    Returns:
        (allowed: bool, reason_code: str, normalized_text: str)
    """
    if not isinstance(raw_text, str):
        return False, "INVALID_TYPE", ""

    normalized = normalize_text(raw_text)

    # 1. Length validation
    if not normalized:
        return False, "EMPTY_INPUT", ""

    if len(normalized) > max_length:
        return False, "LENGTH_EXCEEDED", ""

    # 2. Repeated character floods (e.g. 'aaaaaaaaaaaaaaaa...')
    if RE_REPEATED_CHARS.search(normalized):
        return False, "CHARACTER_FLOOD", ""

    # 3. Hexadecimal blob detection (check before base64 since hex is a subset of base64 chars)
    if is_hex_blob(normalized):
        return False, "HEX_BLOB", ""

    # 4. Base64 encoded payload detection
    if is_base64_blob(normalized):
        return False, "BASE64_BLOB", ""

    # 5. Prompt injection detection across English, Tamil, and Tanglish
    for pattern in ALL_INJECTION_REGEX:
        if pattern.search(normalized):
            return False, "PROMPT_INJECTION", ""

    return True, "ALLOWED", normalized

