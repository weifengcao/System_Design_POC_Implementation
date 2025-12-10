from __future__ import annotations

import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List

from . import models, schemas


def _parse_decimal(value: str) -> bool:
    try:
        Decimal(value.replace(",", "").strip())
        return True
    except (InvalidOperation, AttributeError):
        return False


def _parse_date(value: str) -> bool:
    if not value:
        return False
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            datetime.strptime(value.strip(), fmt)
            return True
        except ValueError:
            continue
    return False


def _status(found: bool, valid: bool) -> str:
    if not found:
        return "failed"
    return "passed" if valid else "failed"


def _parse_line_items(text: str) -> List[dict]:
    """
    Heuristic table parser for invoice line items.
    Expects lines like: "Widget A 2 9.99 19.98" (desc qty unit total)
    """
    items: List[dict] = []
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) < 4:
            continue
        try:
            qty = float(parts[-3])
            unit_price = float(parts[-2])
            amount = float(parts[-1])
        except ValueError:
            continue
        desc = " ".join(parts[:-3])
        if not desc:
            continue
        items.append(
            {
                "description": desc,
                "qty": qty,
                "unit_price": unit_price,
                "amount": amount,
            }
        )
    return items


def _extract_fields_from_text(full_text: str, default_conf: float, page_count: int, doc_type: str) -> List[models.FieldEntry]:
    """
    Heuristic field extraction for invoices; fall back to generic fields for other types.
    """
    fields: List[models.FieldEntry] = []
    if doc_type.lower() != "invoice":
        fields.append(
            models.FieldEntry(
                name="full_text",
                value=full_text,
                bbox=None,
                confidence=default_conf,
                validator_status="skipped",
            )
        )
        fields.append(
            models.FieldEntry(
                name="page_count",
                value=str(page_count),
                bbox=None,
                confidence=1.0,
                validator_status="passed",
            )
        )
        return fields

    invoice_match = re.search(r"(INV[-\s]?\d+)", full_text, re.IGNORECASE)
    total_match = re.search(r"total[^0-9]*([\d,.]+)", full_text, re.IGNORECASE)

    fields.append(
        models.FieldEntry(
            name="invoice_number",
            value=invoice_match.group(1) if invoice_match else "N/A",
            bbox=None,
            confidence=default_conf if invoice_match else default_conf * 0.5,
            validator_status="skipped",
        )
    )
    total_value = "0.00"
    total_conf = default_conf * 0.5
    total_status = "skipped"
    if total_match:
        total_value = total_match.group(1)
        total_conf = default_conf
        try:
            # strip commas and normalize
            _ = Decimal(total_value.replace(",", ""))
            total_status = "passed"
        except (InvalidOperation, AttributeError):
            total_status = "failed"

    fields.append(
        models.FieldEntry(
            name="total",
            value=total_value,
            bbox=None,
            confidence=total_conf,
            validator_status=total_status,  # basic numeric validation
        )
    )
    fields.append(
        models.FieldEntry(
            name="page_count",
            value=str(page_count),
            bbox=None,
            confidence=1.0,
            validator_status="passed",
        )
    )
    fields.append(
        models.FieldEntry(
            name="full_text",
            value=full_text,
            bbox=None,
            confidence=default_conf,
            validator_status="skipped",
        )
    )
    return fields


def extract_fields(full_text: str, doc_type: str, default_conf: float, page_count: int) -> List[models.FieldEntry]:
    """
    Schema-driven extraction with simple heuristics per doc_type.
    """
    return _extract_fields_from_text(full_text, default_conf, page_count, doc_type)
