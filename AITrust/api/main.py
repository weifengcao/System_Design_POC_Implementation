import logging
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status

from AITrust.core.audit import write_audit_log
from AITrust.core.cache import cache_client
from AITrust.core.config import get_settings
from AITrust.core.models import CheckRequest, TrustResponse
from AITrust.core.policy import policy_engine
from AITrust.core.scanner import pii_scan_task
from AITrust.core.storage import init_db

logger = logging.getLogger("aitrust")
settings = get_settings()

app = FastAPI(title=settings.APP_NAME, version=settings.VERSION)


async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    if x_api_key != settings.AITRUST_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return x_api_key


@app.on_event("startup")
async def startup_event() -> None:
    await init_db()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.VERSION}


async def _get_cached_response(text: str) -> Optional[TrustResponse]:
    try:
        cached_payload = await cache_client.get_verdict(text)
        if not cached_payload:
            return None
        return TrustResponse(**cached_payload)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.warning("Cache unavailable: %s", exc)
        return None


async def _cache_response(text: str, response: TrustResponse) -> None:
    try:
        await cache_client.set_verdict(text, response.model_dump(mode="json"))
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.warning("Cache set failed: %s", exc)


@app.post("/check", response_model=TrustResponse)
async def run_check(request: CheckRequest, _: str = Depends(verify_api_key)) -> TrustResponse:
    cached = await _get_cached_response(request.text)
    if cached:
        return cached

    results = policy_engine.run_checks(request.text)
    verdict = "block" if any(result.status == "fail" for result in results) else "allow"
    response = TrustResponse(
        request_id=request.request_id,
        verdict=verdict,
        results=results,
    )

    await _cache_response(request.text, response)
    try:
        await write_audit_log(request, response)
    except Exception as exc:  # pragma: no cover - fail open
        logger.error("Audit log failed: %s", exc)

    pii_scan_task.delay(request.model_dump())
    return response
