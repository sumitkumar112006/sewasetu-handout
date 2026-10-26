# -*- coding: utf-8 -*-
"""
Unicode-aware input sanitization module for Sewa Setu.
Handles full UTF-8 Indic scripts (Assamese, Bengali, Devanagari, etc.)
without corrupting multibyte sequences or byte-level slicing.
"""

import unicodedata
import re

# Strip non-printable control characters (\x00-\x08, \x0b-\x1f, \x7f)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def sanitize(value, maxlen=100):
    """
    Sanitize text input safely:
    1. Returns empty string for None.
    2. Strips surrounding whitespace and non-printable control characters.
    3. Normalizes Unicode into standard NFC canonical form (preserving matras and conjuncts).
    4. Truncates by Unicode character count (not raw UTF-8 bytes) to avoid corrupting
       multibyte characters in Indic scripts (Assamese, Bengali, Devanagari, etc.).
    """
    if value is None:
        return ""

    if not isinstance(value, str):
        value = str(value)

    value = value.strip()
    if not value:
        return ""

    # Canonical Unicode NFC normalization
    value = unicodedata.normalize("NFC", value)

    # Strip control characters
    value = _CONTROL_CHARS_RE.sub("", value)

    # Character-level truncation
    if maxlen is not None and maxlen > 0:
        value = value[:maxlen].strip()

    return value
