from datetime import datetime
from typing import Iterable

from .storage import AuditLogModel, get_session_factory
from .models import CheckRequest, TrustResponse, CheckResult


async def write_audit_log(request: CheckRequest, response: TrustResponse) -> None:
    serialized_results = [
        {
            "check_name": result.check_name,
            "status": result.status,
            "score": result.score,
            "metadata": result.metadata or {},
        }
        for result in response.results
    ]

    audit_entry = AuditLogModel(
        id=response.request_id,
        request_id=response.request_id,
        timestamp=response.timestamp,
        input_text=request.text,
        verdict=response.verdict,
        results_json=serialized_results,
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(audit_entry)
        await session.commit()
