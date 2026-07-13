"""Best-effort redaction for safe errors, summaries, and diagnostics."""

from __future__ import annotations

import re


_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)(authorization\s*:\s*)(?:bearer\s+)?\S+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(key=)[^&\s]+"), r"\1[REDACTED]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bsk-[0-9A-Za-z_-]{16,}\b"), "[REDACTED_SECRET]"),
    (re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"(?i)\b[A-Z]:\\Users\\[^\s]+"), "[REDACTED_PATH]"),
    (re.compile(r"/(?:home|Users)/[^\s]+"), "[REDACTED_PATH]"),
)


def redact_sensitive_text(value: str, secrets: tuple[str, ...] = ()) -> str:
    """Redact common sensitive forms without claiming perfect detection."""

    redacted = value
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    for pattern, replacement in _PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted
