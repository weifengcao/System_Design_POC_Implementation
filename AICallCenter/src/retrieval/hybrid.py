from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ..services.knowledge import Document, KnowledgeBase


@dataclass
class RetrievalResult:
    documents: List[Document]


class HybridRetriever:
    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self.knowledge_base = knowledge_base

    def retrieve(self, query: str, top_k: int = 3) -> RetrievalResult:
        docs = self.knowledge_base.search(query, limit=top_k)
        if not docs:
            docs = self.knowledge_base.search("general help", limit=1)
        return RetrievalResult(documents=docs)

