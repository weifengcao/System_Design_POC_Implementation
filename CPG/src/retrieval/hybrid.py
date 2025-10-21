from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Protocol


class VectorStore(Protocol):
    def similarity_search(self, query: str, *, top_k: int, metadata: Dict[str, str] | None = None) -> List[Dict[str, object]]:
        ...


class GraphStore(Protocol):
    def neighbors(self, node_id: str, relation: str) -> List[str]:
        ...


@dataclass
class RetrievalResult:
    documents: List[Dict[str, object]]
    citations: List[str]
    debug: Dict[str, object]


class HybridRetriever:
    """Coordinates vector and graph queries (placeholder for LangChain retriever)."""

    def __init__(self, vector_store: VectorStore, graph_store: GraphStore) -> None:
        self.vector_store = vector_store
        self.graph_store = graph_store

    def retrieve(self, query: str, *, seed_nodes: List[str] | None = None, top_k: int = 5) -> RetrievalResult:
        docs = self.vector_store.similarity_search(query, top_k=top_k)
        citations: List[str] = []
        graph_hits: Dict[str, List[str]] = {}
        for node in seed_nodes or []:
            related = self.graph_store.neighbors(node, "eligible_supplier")
            graph_hits[node] = related
            citations.extend(related)
        return RetrievalResult(documents=docs, citations=citations, debug={"graph_hits": graph_hits})

