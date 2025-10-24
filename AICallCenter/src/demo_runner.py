from __future__ import annotations

from pathlib import Path

from .orchestrator import build_orchestrator


def run_demo() -> None:
    base_path = Path(__file__).resolve().parents[1]
    orchestrator = build_orchestrator(base_path)
    conversation_id = "conv-001"
    orchestrator.start_conversation(conversation_id)

    print("Customer: Hi, I want to check the status of my order 12345.")
    response = orchestrator.send_user_message(conversation_id, "Hi, I want to check the status of my order 12345.")
    print(f"AI: {response}")

    print("Customer: Also, I was double charged on my credit card.")
    response = orchestrator.send_user_message(conversation_id, "Also, I was double charged on my credit card.", sentiment=-0.5)
    print(f"AI: {response}")

    orchestrator.end_conversation(conversation_id, sentiment=-0.4)
    context = orchestrator.contexts[conversation_id]
    print("\nTranscript:")
    for line in context.transcript:
        print(line)


if __name__ == "__main__":
    run_demo()

