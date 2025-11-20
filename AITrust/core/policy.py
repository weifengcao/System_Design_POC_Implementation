import re
from typing import List

from .models import CheckResult


class PolicyEngine:
    """Collection of lightweight synchronous safety checks."""

    def __init__(self):
        self.banned_keywords = {"bomb", "explosive", "password", "ssn", "hack"}
        self.prompt_injection_markers = [
            r"ignore\s+(previous|prior)\s+instructions",
            r"disregard\s+all\s+rules",
        ]
        self.email_regex = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

    def _keyword_check(self, text: str) -> CheckResult:
        lowered = text.lower()
        hit = any(keyword in lowered for keyword in self.banned_keywords)
        status = "fail" if hit else "pass"
        metadata = {"matched_keyword": hit}
        return CheckResult(
            check_name="keyword_filter",
            status=status,
            score=0.0 if hit else 1.0,
            metadata=metadata,
        )

    def _prompt_injection_check(self, text: str) -> CheckResult:
        match = any(re.search(pattern, text, re.IGNORECASE) for pattern in self.prompt_injection_markers)
        status = "fail" if match else "pass"
        metadata = {"pattern_matched": match}
        return CheckResult(
            check_name="prompt_injection",
            status=status,
            score=0.0 if match else 1.0,
            metadata=metadata,
        )

    def _pii_check(self, text: str) -> CheckResult:
        match = self.email_regex.search(text)
        status = "warn" if match else "pass"
        metadata = {"email_detected": bool(match)}
        return CheckResult(
            check_name="pii_scanner",
            status=status,
            score=0.5 if match else 1.0,
            metadata=metadata,
        )

    def run_checks(self, text: str) -> List[CheckResult]:
        return [
            self._keyword_check(text),
            self._prompt_injection_check(text),
            self._pii_check(text),
        ]


policy_engine = PolicyEngine()
