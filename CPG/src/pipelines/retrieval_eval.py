from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List


@dataclass
class RetrievalQuery:
    query: str
    expected_doc_ids: List[str]


class RetrievalEvaluator:
    def __init__(self, retriever: Callable[[str], List[str]]) -> None:
        self.retriever = retriever

    def evaluate(self, queries: List[RetrievalQuery]) -> float:
        hits = 0
        total = len(queries)
        for q in queries:
            results = self.retriever(q.query)
            if any(doc_id in results for doc_id in q.expected_doc_ids):
                hits += 1
        return hits / total if total else 0.0

