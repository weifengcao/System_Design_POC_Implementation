from datetime import datetime, timezone
from typing import Dict, Any, List

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import AnonymizerRequest, OperatorConfig

from .celery_app import celery_app

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()


def _anonymize(text: str, results: List[Any]) -> str:
    return anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators={"DEFAULT": OperatorConfig("replace", {"new_value": "<REDACTED>"})},
    )


@celery_app.task(name="core.scanner.pii_scan_task")
def pii_scan_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scans text for PII using Presidio and returns a summary of findings.
    """
    text = payload.get("text", "")
    if not text:
        return {}

    analyzer_results = analyzer.analyze(text=text, language="en")
    anonymized_text = _anonymize(text, analyzer_results)

    pii_found = [res.to_dict() for res in analyzer_results]

    return {
        "request_id": payload.get("request_id"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pii_found": pii_found,
        "anonymized_text": anonymized_text,
        "status": "pii_detected" if pii_found else "pii_not_detected",
    }