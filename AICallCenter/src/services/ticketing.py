from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class Ticket:
    ticket_id: str
    subject: str
    status: str


class TicketingService:
    def __init__(self) -> None:
        self._tickets: Dict[str, Ticket] = {}
        self._counter = 1

    def create_ticket(self, subject: str) -> Ticket:
        ticket_id = f"T-{self._counter:05d}"
        self._counter += 1
        ticket = Ticket(ticket_id=ticket_id, subject=subject, status="open")
        self._tickets[ticket_id] = ticket
        return ticket

