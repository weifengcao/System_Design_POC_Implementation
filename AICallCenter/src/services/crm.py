from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class CustomerRecord:
    customer_id: str
    name: str
    email: str
    orders: Dict[str, str]


class CRMService:
    def __init__(self) -> None:
        self._records = {
            "123": CustomerRecord(customer_id="123", name="Alice Johnson", email="alice@example.com", orders={"12345": "In Transit"})
        }

    def lookup_customer(self, identifier: str) -> CustomerRecord | None:
        return self._records.get(identifier)

