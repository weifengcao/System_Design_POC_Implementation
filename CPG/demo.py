from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.coordinator import load_purchase_order, load_default_environment
from src.pipelines.retrieval_eval import RetrievalQuery


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CPG procurement copilot demo")
    parser.add_argument(
        "--po-file",
        type=Path,
        default=Path(__file__).parent / "data" / "purchase_orders" / "sample_po.json",
        help="Path to purchase order JSON",
    )
    parser.add_argument("--verbose", action="store_true", help="Print agent conversation log")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    orchestrator = load_default_environment(Path(__file__).parent)
    purchase_order = load_purchase_order(args.po_file)
    orchestrator.register_po(purchase_order)
    context = orchestrator.start(purchase_order["po_id"])

    report = context.shared_state.get("report", {})
    print(json.dumps(report, indent=2))

    workflow_state = orchestrator.workflow.get_workflow(purchase_order["po_id"])
    print("\n--- Workflow State ---")
    for task_name, record in workflow_state.tasks.items():
        print(f"{task_name}: {record.state.value}")

    eval_score = orchestrator.retrieval_metrics.evaluate(
        [
            RetrievalQuery(query="ISO 13485 certification requirements", expected_doc_ids=["policies"]),
            RetrievalQuery(query="negotiation tactics packaging", expected_doc_ids=["negotiations"]),
        ]
    )
    print(f"\nRetrieval evaluator hit-rate: {eval_score:.2f}")

    if context.shared_state.get("escalations"):
        print("\n--- Escalations ---")
        for item in context.shared_state["escalations"]:
            print(f"{item['topic']}: {item['payload'].get('issues', [])}")

    if args.verbose:
        print("\n--- Agent Conversation Log ---")
        for message in context.conversation:
            print(f"[{message.sender}] {message.content}")
        print("\n--- Outbound Messages ---")
        for msg in orchestrator.messaging.list_messages():
            print(f"{msg.channel.upper()} -> {msg.supplier_id}: {msg.body.splitlines()[0]}")


if __name__ == "__main__":
    main()
