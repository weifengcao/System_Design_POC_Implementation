from __future__ import annotations

from typing import Dict


class Guardrail:
    """Minimal placeholder for policy enforcement around agent tool use."""

    def validate(self, context: Dict[str, object]) -> bool:
        # Insert PII filtering, regex checks, etc.
        return True


global_guardrail = Guardrail()
