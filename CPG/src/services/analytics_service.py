from __future__ import annotations

from typing import Dict, List

from .supplier_service import Supplier


class AnalyticsService:
    """Utility for computing lightweight sourcing KPIs for the demo."""

    def summarize(self, po: Dict[str, object], suppliers: List[Supplier]) -> Dict[str, object]:
        benchmark = po.get("benchmark_price_per_unit") or 0.0
        quantity = po.get("quantity", 0)
        target_price = po.get("target_price_per_unit") or benchmark

        best_supplier = suppliers[0] if suppliers else None
        if best_supplier:
            candidate_price = min(target_price, benchmark * best_supplier.benchmark_price_index)
        else:
            candidate_price = target_price

        estimated_savings = max(0.0, (benchmark - candidate_price) * quantity)
        diversity_count = sum(1 for supplier in suppliers if supplier.diversity)

        return {
            "po_id": po["po_id"],
            "candidate_supplier": best_supplier.supplier_id if best_supplier else None,
            "estimated_savings": round(estimated_savings, 2),
            "diversity_suppliers": diversity_count,
        }

