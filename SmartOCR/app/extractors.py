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


def extract_fields(full_text: str, doc_type: str, default_conf: float, page_count: int) -> List[models.FieldEntry]:
    """
    Schema-driven extraction with simple heuristics per doc_type.
    """
    schema = schemas.get_schema(doc_type)
    text = full_text or ""
    fields: List[models.FieldEntry] = []

    if schema.doc_type == "invoice":
        invoice_number = re.search(r"(INV[-\s]?\d+)", text, re.IGNORECASE)
        total_match = re.search(r"total[^0-9]*([\d,.]+)", text, re.IGNORECASE)
        tax_match = re.search(r"tax[^0-9]*([\d,.]+)", text, re.IGNORECASE)
        currency_match = re.search(r"\b([A-Z]{3})\b", text)
        vendor_match = re.search(r"vendor[:\s]+([A-Za-z0-9 &.-]+)", text, re.IGNORECASE)
        inv_date_match = re.search(
            r"(invoice date|date)[:\s]+([0-9]{2}/[0-9]{2}/[0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2})",
            text,
            re.IGNORECASE,
        )
        due_date_match = re.search(
            r"(due date)[:\s]+([0-9]{2}/[0-9]{2}/[0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2})",
            text,
            re.IGNORECASE,
        )
        parsed_line_items = _parse_line_items(text)

        for field in schema.fields:
            name = field.name
            value = "N/A"
            confidence = default_conf * 0.5
            status = "failed"

            if name == "invoice_number":
                value = invoice_number.group(1) if invoice_number else "N/A"
                found = invoice_number is not None
                status = _status(found, found)
                confidence = default_conf if found else confidence
            elif name == "total":
                value = total_match.group(1) if total_match else "0.00"
                valid = _parse_decimal(value)
                status = _status(total_match is not None, valid)
                confidence = default_conf if valid else confidence
            elif name == "tax":
                value = tax_match.group(1) if tax_match else "0.00"
                valid = _parse_decimal(value)
                status = _status(tax_match is not None, valid)
                confidence = default_conf if valid else confidence
            elif name == "currency":
                value = currency_match.group(1) if currency_match else "USD"
                status = _status(currency_match is not None, True)
                confidence = default_conf if currency_match else confidence
            elif name == "vendor":
                value = vendor_match.group(1).strip() if vendor_match else "Unknown Vendor"
                status = _status(vendor_match is not None, True)
                confidence = default_conf if vendor_match else confidence
            elif name == "invoice_date":
                raw = inv_date_match.group(2) if inv_date_match else ""
                value = raw or "1970-01-01"
                valid = _parse_date(raw)
                status = _status(inv_date_match is not None, valid)
                confidence = default_conf if valid else confidence
            elif name == "due_date":
                raw = due_date_match.group(2) if due_date_match else ""
                value = raw or "1970-01-01"
                valid = _parse_date(raw)
                status = _status(due_date_match is not None, valid)
                confidence = default_conf if valid else confidence
            elif name == "line_items":
                value = json.dumps(parsed_line_items)
                status = "passed" if parsed_line_items else "failed"
                confidence = default_conf if parsed_line_items else default_conf * 0.3
            else:
                value = "N/A"
                status = "skipped"

            fields.append(
                models.FieldEntry(
                    name=name,
                    value=value,
                    bbox=None,
                    confidence=confidence,
                    validator_status=status,
                )
            )

    else:
        # Generic fallback
        for field in schema.fields:
            val = full_text if field.name == "full_text" else "N/A"
            fields.append(
                models.FieldEntry(
                    name=field.name,
                    value=val,
                    bbox=None,
                    confidence=default_conf,
                    validator_status="skipped",
                )
            )

    # Append page_count for all types
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
