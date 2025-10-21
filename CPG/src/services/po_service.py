from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional


class POService:
    """Lightweight representation of a PO microservice for the hybrid demo."""

    def __init__(self) -> None:
        self._purchase_orders: Dict[str, Dict[str, object]] = {}

    def register_po(self, po: Dict[str, object]) -> None:
        po_id = po["po_id"]
        self._purchase_orders[po_id] = dict(po)

    def load_from_file(self, path: Path) -> Dict[str, object]:
        data = json.loads(path.read_text(encoding="utf-8"))
        self.register_po(data)
        return data

    def get_po(self, po_id: str) -> Optional[Dict[str, object]]:
        return self._purchase_orders.get(po_id)

