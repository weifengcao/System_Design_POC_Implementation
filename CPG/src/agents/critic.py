from __future__ import annotations

from typing import List

from .base import Agent, AgentContext
from ..infrastructure.event_bus import Event
from ..knowledge import KnowledgeBase
from ..services.compliance_service import ComplianceService
from ..services.supplier_service import SupplierService


class CriticAgent(Agent):
    name = "CriticAgent"
    input_topics = ("negotiation.round.completed",)

    def __init__(
        self,
        compliance_service: ComplianceService,
        supplier_service: SupplierService,
        knowledge_base: KnowledgeBase,
    ) -> None:
        self.compliance_service = compliance_service
        self.supplier_service = supplier_service
        self.kb = knowledge_base

    def handle_event(self, event: Event, context: AgentContext) -> List[Event]:
        po = context.shared_state["po"]
        shortlist = context.shared_state.get("shortlist", [])
        suppliers = [
            self.supplier_service.get_supplier(entry["supplier_id"]) for entry in shortlist
        ]
        suppliers = [supplier for supplier in suppliers if supplier]
        verdict = self.compliance_service.evaluate(po, suppliers)
        citations = [doc.doc_id for doc in self.kb.similarity_search("final compliance", top_k=1, filters={"type": "policy"})]

        if verdict.compliant:
            context.add_message(self.name, "Critic validation passed.")
            return [
                Event(
                    topic="negotiation.validated",
                    payload={"po_id": po["po_id"], "round": event.payload["round"], "citations": citations},
                    idempotency_key=f"{po['po_id']}::critic::pass::{event.payload['round']}",
                )
            ]

        issues = verdict.issues + [f"Policy references: {', '.join(citations)}"]
        context.add_message(self.name, "; ".join(issues))
        return [
            Event(
                topic="negotiation.validation_failed",
                payload={"po_id": po["po_id"], "issues": issues},
                idempotency_key=f"{po['po_id']}::critic::fail::{event.payload['round']}",
            )
        ]

