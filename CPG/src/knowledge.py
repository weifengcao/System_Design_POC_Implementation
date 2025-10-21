from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    return TOKEN_PATTERN.findall(text.lower())


def build_vector(tokens: Iterable[str]) -> Dict[str, float]:
    counts: Dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    total = sum(counts.values()) or 1
    return {token: count / total for token, count in counts.items()}


def cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    dot = sum(vec_a.get(token, 0.0) * weight for token, weight in vec_b.items())
    norm_a = math.sqrt(sum(weight * weight for weight in vec_a.values()))
    norm_b = math.sqrt(sum(weight * weight for weight in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class KnowledgeDocument:
    doc_id: str
    content: str
    metadata: Dict[str, str]
    vector: Dict[str, float]


class KnowledgeBase:
    """Hybrid vector + lightweight property graph memory."""

    def __init__(self) -> None:
        self.documents: List[KnowledgeDocument] = []
        self.graph: Dict[str, Dict[str, List[str]]] = {}

    def add_document(self, doc_id: str, content: str, metadata: Dict[str, str]) -> None:
        tokens = tokenize(content)
        vector = build_vector(tokens)
        self.documents.append(
            KnowledgeDocument(doc_id=doc_id, content=content, metadata=metadata, vector=vector)
        )

    def similarity_search(self, query: str, top_k: int = 3, filters: Dict[str, str] | None = None) -> List[KnowledgeDocument]:
        filters = filters or {}
        query_vector = build_vector(tokenize(query))
        scored: List[Tuple[float, KnowledgeDocument]] = []
        for document in self.documents:
            if not self._matches_filters(document, filters):
                continue
            score = cosine_similarity(query_vector, document.vector)
            if score > 0:
                scored.append((score, document))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

    @staticmethod
    def _matches_filters(document: KnowledgeDocument, filters: Dict[str, str]) -> bool:
        for key, value in filters.items():
            if document.metadata.get(key) != value:
                return False
        return True

    def add_relation(self, source: str, relation: str, target: str) -> None:
        node = self.graph.setdefault(source, {})
        node.setdefault(relation, []).append(target)

    def traverse(self, source: str, relation: str) -> List[str]:
        return self.graph.get(source, {}).get(relation, [])

    def remove_document(self, doc_id: str) -> None:
        self.documents = [doc for doc in self.documents if doc.doc_id != doc_id]
        if doc_id in self.graph:
            del self.graph[doc_id]

    def upsert_supplier(self, supplier: Dict[str, object]) -> None:
        doc_id = supplier["supplier_id"]
        self.remove_document(doc_id)
        content = json.dumps(supplier, indent=2)
        metadata = {
            "type": "supplier",
            "supplier_id": supplier["supplier_id"],
            "category": ",".join(supplier["categories"]),
        }
        self.add_document(doc_id, content, metadata)
        # refresh relations
        category_node = f"po_category::{','.join(supplier['categories'])}"
        self.graph.setdefault(category_node, {})["eligible_supplier"] = list(
            {doc_id, *self.graph.get(category_node, {}).get("eligible_supplier", [])}
        )
        self.graph[f"supplier::{doc_id}"] = {
            "certification": [",".join(supplier["certifications"])],
            "region": [",".join(supplier["regions"])],
        }


def load_corpus(base_path: Path) -> KnowledgeBase:
    kb = KnowledgeBase()
    policies = (base_path / "policies.md").read_text(encoding="utf-8")
    kb.add_document("policies", policies, {"type": "policy"})

    negotiations = (base_path / "negotiations.md").read_text(encoding="utf-8")
    kb.add_document("negotiations", negotiations, {"type": "negotiation"})

    suppliers_data = json.loads((base_path / "suppliers.json").read_text(encoding="utf-8"))
    for supplier in suppliers_data:
        content = json.dumps(supplier, indent=2)
        metadata = {
            "type": "supplier",
            "supplier_id": supplier["supplier_id"],
            "category": ",".join(supplier["categories"]),
        }
        kb.add_document(supplier["supplier_id"], content, metadata)
        kb.add_relation(f"po_category::{','.join(supplier['categories'])}", "eligible_supplier", supplier["supplier_id"])
        kb.add_relation(f"supplier::{supplier['supplier_id']}", "certification", ",".join(supplier["certifications"]))
        kb.add_relation(f"supplier::{supplier['supplier_id']}", "region", ",".join(supplier["regions"]))
    return kb
