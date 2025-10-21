from __future__ import annotations

from typing import List

from .base import Agent, AgentContext
from ..infrastructure.event_bus import Event
from ..knowledge import KnowledgeBase
from ..services.compliance_service import ComplianceService
from ..services.supplier_service import SupplierService


class ComplianceSentinelAgent(Agent):
    name = "ComplianceSentinelAgent"
    input_topics = ("supplier.shortlist.created",)

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
        po_id = event.payload["po_id"]
        shortlist_payload = event.payload["shortlist"]
        context.shared_state["shortlist"] = shortlist_payload
        supplier_objs = [
            self.supplier_service.get_supplier(entry["supplier_id"])
            for entry in shortlist_payload
        ]
        supplier_objs = [supplier for supplier in supplier_objs if supplier]

        po = context.shared_state["po"]
        result = self.compliance_service.evaluate(po, supplier_objs)
        issues = list(result.issues)

        if issues:
            issues.extend(self._policy_citations(issues))
            context.shared_state["compliance_issues"] = issues
            context.add_message(self.name, "; ".join(issues))
            return [
                Event(
                    topic="compliance.failed",
                    payload={"po_id": po_id, "issues": issues},
                    idempotency_key=f"{po_id}::compliance::fail",
                )
            ]
        context.shared_state["compliance_issues"] = []
        context.add_message(self.name, "Compliance clearance achieved.")
        return [
            Event(
                topic="compliance.approved",
                payload={"po_id": po_id, "shortlist": shortlist_payload},
                idempotency_key=f"{po_id}::compliance::pass",
            )
        ]

    def _policy_citations(self, issues: List[str]) -> List[str]:
        citations: List[str] = []
        for issue in issues:
            docs = self.kb.similarity_search(issue, top_k=1, filters={"type": "policy"})
            if docs:
                citations.append(f"Reference: {docs[0].doc_id}")
        return citations
