from __future__ import annotations

from typing import Dict, List

from .base import Agent, AgentContext
from ..infrastructure.event_bus import Event
from ..services.supplier_service import Supplier, SupplierService
from ..retrieval.hybrid import HybridRetriever


class SourcingScoutAgent(Agent):
    name = "SourcingScoutAgent"
    input_topics = ("task.plan.completed",)

    def __init__(self, supplier_service: SupplierService, retriever: HybridRetriever) -> None:
        self.supplier_service = supplier_service
        self.retriever = retriever

    def handle_event(self, event: Event, context: AgentContext) -> List[Event]:
        po_id = event.payload["po_id"]
        plan = event.payload["plan"]
        context.shared_state["plan"] = plan
        requires_diversity = any(task.get("requires_diversity") for task in plan["tasks"])
        po = context.shared_state["po"]

        suppliers = self.supplier_service.search_suppliers(
            category=po["category"],
            region=po["region"],
            required_certifications=po.get("required_certifications", []),
            require_diversity=requires_diversity,
        )

        shortlist = [
            self._build_supplier_entry(po, supplier, plan)
            for supplier in suppliers
        ]

        context.shared_state["shortlist"] = shortlist
        context.add_message(self.name, f"Ranked {len(shortlist)} suppliers for category {po['category']}")
        self.supplier_service.record_shortlist(po_id, shortlist)

        idempotency_key = f"{po_id}::shortlist"
        return [
            Event(
                topic="supplier.shortlist.created",
                payload={"po_id": po_id, "shortlist": shortlist},
                idempotency_key=idempotency_key,
            )
        ]

    def _build_supplier_entry(
        self,
        po: Dict[str, object],
        supplier: Supplier,
        plan: Dict[str, object],
    ) -> Dict[str, object]:
        query = (
            f"supplier {supplier.name} {supplier.supplier_id} risk {supplier.risk_score} "
            f"category {', '.join(supplier.categories)} certifications {supplier.certifications}"
        )
        result = self.retriever.retrieve(query, seed_nodes=[f"supplier::{supplier.supplier_id}"], top_k=1)
        justification = result.documents[0]["content"] if result.documents else supplier.notes or "No justification available."
        return {
            "supplier_id": supplier.supplier_id,
            "name": supplier.name,
            "email": supplier.email,
            "price_index": supplier.benchmark_price_index,
            "risk_score": supplier.risk_score,
            "diversity": supplier.diversity,
            "notes": supplier.notes,
            "justification": justification,
        }
