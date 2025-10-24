from __future__ import annotations

import re
from typing import Dict


SENSITIVE_PATTERN = re.compile(r"\b(\d{3}-?\d{2}-?\d{4}|\d{16})\b")


def enforce_guardrails(text: str) -> str:
    if SENSITIVE_PATTERN.search(text):
        return "I'm unable to continue. Let me connect you with a specialist."
    return text


def should_escalate(metadata: Dict[str, str]) -> bool:
    flags = {metadata.get("sentiment"), metadata.get("policy")} - {None}
    return bool(flags)

