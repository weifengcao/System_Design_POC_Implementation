from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

from ..pipelines.cdc import CDCEvent, CDCIngestionPipeline


@dataclass
class Supplier:
    supplier_id: str
    name: str
    categories: List[str]
    regions: List[str]
    diversity: List[str]
    certifications: List[str]
    benchmark_price_index: float
    risk_score: float
    email: str
    notes: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)


class SupplierService:
    """Simulates a supplier registry microservice with search and shortlist recording."""

    def __init__(self, cdc_pipeline: CDCIngestionPipeline | None = None) -> None:
        self._suppliers: Dict[str, Supplier] = {}
        self._shortlists: Dict[str, List[Dict[str, object]]] = {}
        self._cdc = cdc_pipeline

    def load_from_file(self, path: Path) -> None:
        raw_suppliers = json.loads(path.read_text(encoding="utf-8"))
        for raw in raw_suppliers:
            supplier = Supplier(**raw)
            self._suppliers[supplier.supplier_id] = supplier
            if self._cdc:
                self._cdc.emit(CDCEvent(entity="supplier", entity_id=supplier.supplier_id, operation="upsert", payload=asdict(supplier)))

    def search_suppliers(
        self,
        *,
        category: str,
        region: str,
        required_certifications: List[str],
        require_diversity: bool,
    ) -> List[Supplier]:
        matches: List[Supplier] = []
        for supplier in self._suppliers.values():
            if category not in supplier.categories:
                continue
            if region not in supplier.regions:
                continue
            if not all(cert in supplier.certifications for cert in required_certifications):
                continue
            if require_diversity and not supplier.diversity:
                continue
            matches.append(supplier)
        matches.sort(key=lambda s: (s.benchmark_price_index, s.risk_score))
        return matches

    def record_shortlist(self, po_id: str, suppliers: List[Dict[str, object]]) -> None:
        self._shortlists[po_id] = suppliers

    def get_supplier(self, supplier_id: str) -> Optional[Supplier]:
        return self._suppliers.get(supplier_id)

    def get_shortlist(self, po_id: str) -> List[Dict[str, object]]:
        return self._shortlists.get(po_id, [])

    def update_supplier_risk(self, supplier_id: str, risk_score: float, notes: Optional[str] = None) -> Supplier:
        supplier = self._suppliers[supplier_id]
        supplier.risk_score = risk_score
        if notes:
            supplier.notes = notes
        if self._cdc:
            self._cdc.emit(CDCEvent(entity="supplier", entity_id=supplier_id, operation="update", payload=asdict(supplier)))
        return supplier
