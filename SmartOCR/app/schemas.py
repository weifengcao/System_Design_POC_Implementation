from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class FieldSchema:
    name: str
    description: str
    required: bool = True


@dataclass
class DocumentSchema:
    doc_type: str
    fields: List[FieldSchema] = field(default_factory=list)


INVOICE_SCHEMA = DocumentSchema(
    doc_type="invoice",
    fields=[
        FieldSchema("vendor", "Supplier name"),
        FieldSchema("invoice_number", "Invoice identifier"),
        FieldSchema("invoice_date", "Date of invoice"),
        FieldSchema("due_date", "Payment due date"),
        FieldSchema("currency", "ISO currency code"),
        FieldSchema("total", "Grand total amount"),
        FieldSchema("tax", "Total tax"),
        FieldSchema("line_items", "Line items with desc/qty/unit price/amount"),
    ],
)


GENERIC_SCHEMA = DocumentSchema(
    doc_type="generic",
    fields=[FieldSchema("full_text", "Full OCR text", required=False)],
)


SCHEMAS = {s.doc_type: s for s in [INVOICE_SCHEMA, GENERIC_SCHEMA]}


def get_schema(doc_type: str) -> DocumentSchema:
    return SCHEMAS.get(doc_type, GENERIC_SCHEMA)
