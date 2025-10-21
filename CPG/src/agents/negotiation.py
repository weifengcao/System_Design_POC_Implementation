from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from .base import Agent, AgentContext
from ..infrastructure.event_bus import Event
from ..infrastructure.guardrails import global_guardrail
from ..services.messaging_service import MessagingService
from ..retrieval.hybrid import HybridRetriever


class NegotiatorAgent(Agent):
    name = "NegotiatorAgent"
    input_topics = ("compliance.approved", "negotiation.response.received")

    def __init__(self, messaging_service: MessagingService, retriever: HybridRetriever) -> None:
        self.messaging = messaging_service
        self.retriever = retriever

    def handle_event(self, event: Event, context: AgentContext) -> List[Event]:
        po = context.shared_state["po"]
        shortlist = event.payload.get("shortlist") or context.shared_state.get("shortlist", [])
        round_id = event.payload.get("round", 1)

        retrieval = self.retriever.retrieve(
            f"negotiation tactics {po['category']} discount sustainability",
            top_k=1,
        )
        snippet_text = retrieval.documents[0]["content"] if retrieval.documents else ""

        packets = []
        for supplier in shortlist:
            email = self._draft_email(po, supplier, snippet_text, round_id)
            if global_guardrail.validate({"email": email}):
                self.messaging.send_email(
                    po_id=po["po_id"], supplier_id=supplier["supplier_id"], body=email
                )
            packets.append(
                {
                    "supplier_id": supplier["supplier_id"],
                    "target_price": supplier["price_index"] * po["benchmark_price_per_unit"],
                    "round": round_id,
                    "email": email,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        context.shared_state.setdefault("negotiation_packets", []).extend(packets)
        context.add_message(self.name, f"Executed negotiation round {round_id}")

        return [
            Event(
                topic="negotiation.round.completed",
                payload={"po_id": po["po_id"], "round": round_id, "packets": packets},
                idempotency_key=f"{po['po_id']}::negotiation::{round_id}",
            )
        ]

    def _draft_email(
        self,
        po: Dict[str, object],
        supplier: Dict[str, object],
        snippet: str,
        round_id: int,
    ) -> str:
        highlights = [
            f"Round {round_id} for PO {po['po_id']} seeking {po['quantity']} units.",
            f"Target sustainability-aligned pricing benchmark ${po['benchmark_price_per_unit']:.2f}.",
            f"Timeline requirement: {po['timeline_weeks']} weeks to {po['region']}.",
        ]
        if supplier["diversity"]:
            highlights.append("We value your diversity certifications in this evaluation.")
        negotiation_tip = snippet.splitlines()[0] if snippet else "Please outline tiered pricing options."
        body = "\n".join(highlights)
        return (
            f"Subject: RFQ follow-up - {po['description']} (Round {round_id})\n"
            f"To: {supplier['email']}\n\n"
            f"Hello {supplier['name']},\n\n"
            f"{body}\n\n"
            f"{negotiation_tip}\n\n"
            "Regards,\nCPG Procurement Copilot"
        )
