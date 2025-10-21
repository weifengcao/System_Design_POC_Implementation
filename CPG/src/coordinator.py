from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from .agents.base import Agent, AgentContext
from .agents.compliance import ComplianceSentinelAgent
from .agents.critic import CriticAgent
from .agents.escalation import EscalationAgent
from .agents.negotiation import NegotiatorAgent
from .agents.planner import PlannerAgent
from .agents.reporter import InsightsReporterAgent
from .agents.sourcing import SourcingScoutAgent
from .infrastructure.event_bus import Event, EventBus
from .infrastructure.idempotency import IdempotencyRegistry
from .infrastructure.workflow import TaskState, WorkflowEngine
from .knowledge import KnowledgeBase, load_corpus
from .pipelines.cdc import CDCEvent, CDCIngestionPipeline
from .pipelines.retrieval_eval import RetrievalEvaluator, RetrievalQuery
from .services.analytics_service import AnalyticsService
from .services.compliance_service import ComplianceService
from .services.messaging_service import MessagingService
from .services.po_service import POService
from .services.supplier_service import SupplierService
from .retrieval.adapters import KnowledgeGraphAdapter, KnowledgeVectorAdapter
from .retrieval.hybrid import HybridRetriever


class AgentOrchestrator:
    """Event-driven orchestrator approximating Temporal + Kafka behavior."""

    def __init__(
        self,
        *,
        po_service: POService,
        supplier_service: SupplierService,
        compliance_service: ComplianceService,
        analytics_service: AnalyticsService,
        messaging_service: MessagingService,
        workflow_engine: WorkflowEngine,
        event_bus: EventBus,
        idempotency: IdempotencyRegistry,
        knowledge_base: KnowledgeBase,
        cdc_pipeline: CDCIngestionPipeline,
    ) -> None:
        self.po_service = po_service
        self.supplier_service = supplier_service
        self.compliance_service = compliance_service
        self.analytics_service = analytics_service
        self.messaging_service = messaging_service
        self.workflow_engine = workflow_engine
        self.event_bus = event_bus
        self.idempotency = idempotency
        self.knowledge_base = knowledge_base
        self.contexts: Dict[str, AgentContext] = {}
        self.cdc_pipeline = cdc_pipeline
        self.vector_adapter = KnowledgeVectorAdapter(knowledge_base)
        self.graph_adapter = KnowledgeGraphAdapter(knowledge_base)
        self.retriever = HybridRetriever(self.vector_adapter, self.graph_adapter)
        self.retrieval_evaluator = RetrievalEvaluator(lambda query: [doc["doc_id"] for doc in self.vector_adapter.similarity_search(query, top_k=5)])

        agents: Dict[str, Agent] = {
            "planner": PlannerAgent(po_service, workflow_engine, knowledge_base),
            "sourcing": SourcingScoutAgent(supplier_service, self.retriever),
            "compliance": ComplianceSentinelAgent(compliance_service, supplier_service, knowledge_base),
            "negotiator": NegotiatorAgent(messaging_service, self.retriever),
            "critic": CriticAgent(compliance_service, supplier_service, knowledge_base),
            "reporter": InsightsReporterAgent(analytics_service, supplier_service),
            "escalation": EscalationAgent(),
        }
        self.agents = agents
        self._register_agents()
        self.workflow_transitions = {
            "task.plan.completed": ("supplier_shortlist", TaskState.IN_PROGRESS),
            "supplier.shortlist.created": ("supplier_shortlist", TaskState.COMPLETED),
            "compliance.approved": ("compliance_review", TaskState.COMPLETED),
            "compliance.failed": ("compliance_review", TaskState.FAILED),
            "negotiation.round.completed": ("negotiation_campaign", TaskState.IN_PROGRESS),
            "negotiation.validated": ("negotiation_campaign", TaskState.COMPLETED),
            "report.ready": ("insights_summary", TaskState.COMPLETED),
        }

    def _register_agents(self) -> None:
        for agent in self.agents.values():
            for topic in agent.input_topics:
                self.event_bus.subscribe(topic, self._wrap_handler(agent))

    def _wrap_handler(self, agent: Agent):
        def handler(event: Event):
            po_id = event.payload["po_id"]
            context = self.contexts.setdefault(po_id, AgentContext(po_id=po_id))
            context.shared_state.setdefault("po", self.po_service.get_po(po_id))
            if not self.idempotency.check_and_set(event.idempotency_key or event.event_id, agent.name):
                return []
            results = agent.handle_event(event, context)
            self._advance_workflow(po_id, event.topic)
            for produced in results:
                self._advance_workflow(po_id, produced.topic)
            return results

        return handler

    def register_po(self, purchase_order: dict) -> None:
        self.po_service.register_po(purchase_order)
        po_id = purchase_order["po_id"]
        self.contexts[po_id] = AgentContext(po_id=po_id, shared_state={"po": purchase_order})

    def start(self, po_id: str) -> AgentContext:
        if po_id not in self.contexts:
            raise ValueError(f"PO {po_id} not registered")
        self.workflow_engine.create_workflow(po_id, ["supplier_shortlist", "compliance_review", "negotiation_campaign", "insights_summary"])
        initial_event = Event(topic="po.created", payload={"po_id": po_id}, idempotency_key=f"{po_id}::created")
        self.event_bus.publish(initial_event)
        return self.contexts[po_id]

    @property
    def messaging(self) -> MessagingService:
        return self.messaging_service

    @property
    def workflow(self) -> WorkflowEngine:
        return self.workflow_engine

    @property
    def retrieval_metrics(self) -> RetrievalEvaluator:
        return self.retrieval_evaluator

    def _advance_workflow(self, po_id: str, topic: str) -> None:
        transition = self.workflow_transitions.get(topic)
        if not transition:
            return
        task_name, new_state = transition
        self.workflow_engine.update_task(po_id, task_name, new_state)


def load_purchase_order(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_default_environment(base_path: Path) -> AgentOrchestrator:
    knowledge_base = load_corpus(base_path / "data" / "knowledge")
    po_service = POService()
    cdc_pipeline = CDCIngestionPipeline()
    supplier_service = SupplierService(cdc_pipeline)
    supplier_service.load_from_file(base_path / "data" / "knowledge" / "suppliers.json")
    compliance_service = ComplianceService()
    analytics_service = AnalyticsService()
    messaging_service = MessagingService()
    workflow_engine = WorkflowEngine()
    event_bus = EventBus()
    idempotency = IdempotencyRegistry()

    def handle_cdc(event: CDCEvent) -> None:
        if event.entity == "supplier":
            knowledge_base.upsert_supplier(event.payload)

    cdc_pipeline.register(handle_cdc)

    return AgentOrchestrator(
        po_service=po_service,
        supplier_service=supplier_service,
        compliance_service=compliance_service,
        analytics_service=analytics_service,
        messaging_service=messaging_service,
        workflow_engine=workflow_engine,
        event_bus=event_bus,
        idempotency=idempotency,
        knowledge_base=knowledge_base,
        cdc_pipeline=cdc_pipeline,
    )
