from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .supplier_service import Supplier


@dataclass
class ComplianceResult:
    compliant: bool
    issues: List[str]


class ComplianceService:
    """Rule-based compliance evaluation resembling a dedicated service."""

    def evaluate(self, po: Dict[str, object], suppliers: List[Supplier]) -> ComplianceResult:
        issues: List[str] = []
        budget = po.get("budget_ceiling")
        if budget and budget > 250000:
            issues.append("Spend above $250k requires VP approval.")
        if budget and budget > 1_000_000 and len(suppliers) < 2:
            issues.append("High-spend event must include at least two qualified suppliers.")

        for supplier in suppliers:
            if "probation" in supplier.notes.lower():
                issues.append(f"{supplier.name} on probation; Compliance review required.")

        if po.get("category") == "life_sciences":
            missing_iso = [
                supplier.name for supplier in suppliers if "ISO 13485" not in supplier.certifications
            ]
            if missing_iso:
                issues.append(f"Missing ISO 13485 certification: {', '.join(missing_iso)}.")

        return ComplianceResult(compliant=not issues, issues=issues)
