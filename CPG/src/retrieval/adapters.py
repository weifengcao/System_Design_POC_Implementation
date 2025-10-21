from __future__ import annotations

from typing import Dict, List

from ..knowledge import KnowledgeBase


class KnowledgeVectorAdapter:
    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self.kb = knowledge_base

    def similarity_search(self, query: str, *, top_k: int, metadata: Dict[str, str] | None = None) -> List[Dict[str, object]]:
        docs = self.kb.similarity_search(query, top_k=top_k, filters=metadata)
        return [
            {
                "doc_id": doc.doc_id,
                "content": doc.content,
                "metadata": doc.metadata,
            }
            for doc in docs
        ]


class KnowledgeGraphAdapter:
    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self.kb = knowledge_base

    def neighbors(self, node_id: str, relation: str) -> List[str]:
        return self.kb.traverse(node_id, relation)

