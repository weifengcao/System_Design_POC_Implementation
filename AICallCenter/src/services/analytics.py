from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ConversationMetrics:
    conversation_id: str
    sentiment: float
    escalated: bool


class AnalyticsService:
    def __init__(self) -> None:
        self._metrics: List[ConversationMetrics] = []

    def record(self, metrics: ConversationMetrics) -> None:
        self._metrics.append(metrics)

    def summary(self) -> Dict[str, float]:
        if not self._metrics:
            return {"count": 0, "avg_sentiment": 0.0, "escalation_rate": 0.0}
        count = len(self._metrics)
        avg_sentiment = sum(m.sentiment for m in self._metrics) / count
        escalations = sum(1 for m in self._metrics if m.escalated)
        return {
            "count": count,
            "avg_sentiment": avg_sentiment,
            "escalation_rate": escalations / count,
        }

