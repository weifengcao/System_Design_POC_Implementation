from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class Document:
    doc_id: str
    content: str
    metadata: Dict[str, str]


class KnowledgeBase:
    def __init__(self) -> None:
        self._documents: List[Document] = []

    def add_document(self, doc_id: str, content: str, metadata: Dict[str, str]) -> None:
        self._documents.append(Document(doc_id=doc_id, content=content, metadata=metadata))

    def search(self, query: str, limit: int = 3) -> List[Document]:
        terms = {token for token in query.lower().split() if len(token) > 2}
        if not terms:
            return []
        scored: List[tuple[int, Document]] = []
        for doc in self._documents:
            content_lower = doc.content.lower()
            score = sum(1 for term in terms if term in content_lower)
            if score:
                doc_type = doc.metadata.get("type")
                if doc_type == "simulation":
                    score *= 3
                elif doc_type == "policy":
                    score *= 2
                elif doc_type == "faq":
                    score *= 1
                scored.append((score, doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored[:limit]]


def load_default_knowledge(base_path: Path) -> KnowledgeBase:
    kb = KnowledgeBase()
    kb.add_document("faqs", (base_path / "faqs.md").read_text(), {"type": "faq"})
    kb.add_document("policies", (base_path / "policies.md").read_text(), {"type": "policy"})
    simulations = json.loads((base_path / "simulations.json").read_text())
    for sim in simulations:
        kb.add_document(sim["intent"], sim["response"], {"type": "simulation", "intent": sim["intent"]})
    return kb
