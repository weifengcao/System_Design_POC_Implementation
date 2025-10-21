from __future__ import annotations

from typing import Iterable, List

from ..models import HealthSignal, StartupProfile


class MonitoringService:
    def evaluate(self, startup: StartupProfile) -> List[HealthSignal]:
        signals: List[HealthSignal] = []

        if startup.portfolio_metrics.runway_months < 9:
            severity = "critical" if startup.portfolio_metrics.runway_months < 6 else "warning"
            signals.append(
                HealthSignal(
                    startup_id=startup.startup_id,
                    severity=severity,
                    indicator="runway",
                    message=f"Runway {startup.portfolio_metrics.runway_months} months.",
                )
            )

        if startup.portfolio_metrics.burn_multiple > 2.5:
            signals.append(
                HealthSignal(
                    startup_id=startup.startup_id,
                    severity="warning",
                    indicator="burn_multiple",
                    message=f"Burn multiple at {startup.portfolio_metrics.burn_multiple}.",
                )
            )

        for signal in startup.signals:
            if signal.type in {"news_sentiment", "social_engagement"} and signal.score < 0.4:
                signals.append(
                    HealthSignal(
                        startup_id=startup.startup_id,
                        severity="info",
                        indicator=signal.type,
                        message=f"Signal {signal.type} flagged score {signal.score}.",
                    )
                )

        return signals

