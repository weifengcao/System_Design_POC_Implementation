from __future__ import annotations

from typing import Dict, List

from .base import Agent, AgentContext
from ..infrastructure.event_bus import Event
from ..infrastructure.workflow import TaskState, WorkflowEngine
from ..knowledge import KnowledgeBase
from ..services.po_service import POService


TASK_ORDER = ["supplier_shortlist", "compliance_review", "negotiation_campaign", "insights_summary"]


class PlannerAgent(Agent):
    name = "PlannerAgent"
    input_topics = ("po.created",)

    def __init__(
        self,
        po_service: POService,
        workflow_engine: WorkflowEngine,
        knowledge_base: KnowledgeBase,
    ) -> None:
        self.po_service = po_service
        self.workflow_engine = workflow_engine
        self.kb = knowledge_base

    def handle_event(self, event: Event, context: AgentContext) -> List[Event]:
        po_id = event.payload["po_id"]
        po = self.po_service.get_po(po_id)
        if not po:
            raise ValueError(f"PlannerAgent: unknown PO {po_id}")

        policy_docs = self.kb.similarity_search(
            f"policies for category {po['category']} budget {po.get('budget_ceiling')}",
            top_k=3,
            filters={"type": "policy"},
        )
        plan = self._build_plan(po, policy_docs)
        workflow = self.workflow_engine.create_workflow(po_id, TASK_ORDER)

        context.shared_state["plan"] = plan
        context.add_message(self.name, f"Initialized workflow with tasks {TASK_ORDER}")

        return [
            Event(
                topic="task.plan.completed",
                payload={"po_id": po_id, "plan": plan, "next_task": workflow.active_task},
                idempotency_key=f"{po_id}::plan",
            )
        ]

    def _build_plan(self, po: Dict[str, object], policies: List) -> Dict[str, object]:
        diversity_pref = "diversity" if "diversity" in po.get("notes", "").lower() else "standard"
        tasks: List[Dict[str, object]] = []
        for task_name in TASK_ORDER:
            tasks.append(
                {
                    "name": task_name,
                    "category_focus": po["category"],
                    "requires_diversity": diversity_pref == "diversity",
                }
            )
        policy_refs = [doc.doc_id for doc in policies]
        return {"tasks": tasks, "policy_refs": policy_refs}
