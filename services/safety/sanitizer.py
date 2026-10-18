"""Untrusted input sanitizer and prompt injection defense wrapper."""
import re
from typing import Dict, Any, List


class InputSanitizer:
    """Treats external logs, documents, and user inputs strictly as non-executable DATA."""

    # Prompt injection and instruction override signatures. Patterns tolerate
    # filler words ("ignore the previous instructions") and separator tricks
    # ("system-prompt-override", "delete-from"). This is a boundary tripwire,
    # not a complete filter: homoglyph/Unicode-obfuscated and novel-synonym
    # attacks can still pass, which is why injection resistance primarily
    # comes from the deterministic architecture never consuming free text as
    # instructions (see docs/security.md).
    SEP = r"[\s\-_]+"
    INJECTION_PATTERNS = [
        rf"(?i)ignore{SEP}(?:\w+{SEP}){{0,3}}?(?:previous|prior|earlier|initial){SEP}instructions?",
        rf"(?i)(?:disregard|forget){SEP}(?:\w+{SEP}){{0,3}}?(?:previous|prior|all){SEP}instructions?",
        rf"(?i)system{SEP}prompt{SEP}override",
        rf"(?i)you{SEP}are{SEP}(?:now{SEP})?in{SEP}developer{SEP}mode",
        rf"(?i)bypass{SEP}(?:all{SEP})?(?:safety|authorization|role)",
        rf"(?i)approve{SEP}(?:all{SEP})?actions{SEP}without{SEP}verification",
        r"(?i)drop(?:\s|/\*.*?\*/)+table",
        rf"(?i)delete{SEP}from",
    ]

    @classmethod
    def detect_injection_attempt(cls, text: str) -> bool:
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, text):
                return True
        return False

    @classmethod
    def sanitize_untrusted_data(cls, raw_data: Any) -> Any:
        if isinstance(raw_data, str):
            # Strip control characters, keep clean text
            cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", raw_data)
            return cleaned.strip()
        elif isinstance(raw_data, dict):
            return {k: cls.sanitize_untrusted_data(v) for k, v in raw_data.items()}
        elif isinstance(raw_data, list):
            return [cls.sanitize_untrusted_data(item) for item in raw_data]
        return raw_data
