from __future__ import annotations

from typing import Dict, List

from .base import Agent, AgentContext
from ..infrastructure.event_bus import Event
from ..services.analytics_service import AnalyticsService
from ..services.supplier_service import SupplierService


class InsightsReporterAgent(Agent):
    name = "InsightsReporterAgent"
    input_topics = ("negotiation.validated",)

    def __init__(self, analytics_service: AnalyticsService, supplier_service: SupplierService) -> None:
        self.analytics_service = analytics_service
        self.supplier_service = supplier_service

    def handle_event(self, event: Event, context: AgentContext) -> List[Event]:
        po = context.shared_state["po"]
        shortlist: List[Dict[str, object]] = context.shared_state.get("shortlist", [])
        negotiations: List[Dict[str, object]] = context.shared_state.get("negotiation_packets", [])
        compliance_issues: List[str] = context.shared_state.get("compliance_issues", [])

        recommendation = self._recommend(shortlist)
        supplier_objs = [
            self.supplier_service.get_supplier(item["supplier_id"]) for item in shortlist
        ]
        supplier_objs = [supplier for supplier in supplier_objs if supplier]
        kpis = self.analytics_service.summarize(po, supplier_objs)

        report = {
            "po_id": po["po_id"],
            "recommended_supplier": recommendation,
            "compliance_flags": compliance_issues,
            "negotiation_drafts": [packet["email"] for packet in negotiations],
            "next_steps": "Review drafts, approve outreach, and schedule supplier calls.",
            "kpis": kpis,
            "citations": event.payload.get("citations", []),
        }
        context.shared_state["report"] = report
        context.add_message(self.name, "Insights report ready for approval.")

        return [
            Event(
                topic="report.ready",
                payload={"po_id": po["po_id"], "report": report},
                idempotency_key=f"{po['po_id']}::report",
            )
        ]

    def _recommend(self, shortlist: List[Dict[str, object]]) -> Dict[str, object] | None:
        if not shortlist:
            return None
        top_supplier = shortlist[0]
        return {
            "supplier_id": top_supplier["supplier_id"],
            "justification": f"Best price index {top_supplier['price_index']} with risk {top_supplier['risk_score']}",
        }

