from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class OutboundMessage:
    po_id: str
    supplier_id: str
    channel: str
    body: str


class MessagingService:
    """Captures agent outbound communication for audit/testing."""

    def __init__(self) -> None:
        self.sent_messages: List[OutboundMessage] = []

    def send_email(self, *, po_id: str, supplier_id: str, body: str) -> None:
        self.sent_messages.append(
            OutboundMessage(po_id=po_id, supplier_id=supplier_id, channel="email", body=body)
        )

    def list_messages(self) -> List[OutboundMessage]:
        return list(self.sent_messages)

