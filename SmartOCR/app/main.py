from __future__ import annotations

from typing import Optional

import anyio
import asyncio
import logging
from fastapi import FastAPI, File, HTTPException, UploadFile, Header
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import models, storage, config, service, ingestion
from .repositories import InMemoryJobRepository
from .queue_backends import InMemoryQueueBackend


app = FastAPI(title="SmartOCR", version="0.1.0")
log = logging.getLogger("smartocr")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

doc_store = storage.InMemoryDocumentStore()
job_repo = InMemoryJobRepository()
job_queue = InMemoryQueueBackend()
object_store = ingestion.ObjectStore()
job_service = service.JobService(docs=doc_store, jobs=job_repo, queue=job_queue)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _check_api_key(x_api_key: Optional[str]) -> None:
    expected = config.settings.api_key
    if expected and x_api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


@app.post("/ocr/extract", response_model=models.OCRResult)
async def extract_ocr(
    file: Optional[UploadFile] = File(default=None),
    payload: Optional[models.SyncExtractRequest] = None,
    x_api_key: Optional[str] = Header(default=None),
    doc_type: str = "generic",
) -> models.OCRResult:
    """
    Sync OCR endpoint. Accepts an uploaded file or a source URL, runs stub pipeline, and returns results.
    """
    _check_api_key(x_api_key)
    if not file and not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a file upload or JSON body with source_url",
        )

    source_uri: str
    content: Optional[bytes] = None
    if file:
        content = await file.read()
        source_uri = file.filename or "uploaded"
        # persist upload to object store for consistency
        try:
            ingestion.validate_upload(content, file.content_type)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        stored_uri = object_store.put(source_uri, content, content_type=file.content_type or "application/octet-stream")
        source_uri = stored_uri
    else:
        assert payload is not None
        source_uri = payload.source_url
        content = await job_service.fetch_bytes(source_uri)

    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty document")

    result = await job_service.process_sync(file_bytes=content, source_uri=source_uri, doc_type=doc_type)
    return result


@app.post("/ocr/jobs", response_model=models.JobCreated)
async def create_job(
    body: models.AsyncJobRequest,
    x_api_key: Optional[str] = Header(default=None),
) -> models.JobCreated:
    _check_api_key(x_api_key)
    # For async jobs with upload URLs, we assume caller provided a reachable URI; validation is deferred to worker fetch.
    return await job_service.create_job(
        source_uri=body.source_url,
        external_id=body.external_id,
        webhook_url=body.webhook_url,
        doc_type=body.doc_type,
        tenant_id=body.tenant_id,
    )


@app.get("/ocr/jobs/{job_id}", response_model=models.JobStatus)
async def get_job(job_id: str, x_api_key: Optional[str] = Header(default=None)) -> models.JobStatus:
    _check_api_key(x_api_key)
    job = await job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return models.JobStatus(
        job_id=job.id,
        status=job.status,
        result=job.result,
        error=job.error,
        doc_type=job.doc_type,
    )


@app.get("/ocr/jobs", response_model=list[models.JobStatus])
async def list_jobs(limit: int = 50, x_api_key: Optional[str] = Header(default=None)) -> list[models.JobStatus]:
    _check_api_key(x_api_key)
    jobs = await job_service.list_jobs(limit=limit)
    return [
        models.JobStatus(
            job_id=j.id,
            status=j.status,
            result=j.result,
            error=j.error,
            doc_type=j.doc_type,
        )
        for j in jobs
    ]


@app.patch("/ocr/jobs/{job_id}/fields", response_model=models.JobStatus)
async def review_job(
    job_id: str,
    body: models.ReviewUpdate,
    x_api_key: Optional[str] = Header(default=None),
) -> models.JobStatus:
    _check_api_key(x_api_key)
    return await job_service.update_review(job_id=job_id, fields=body.fields)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):  # type: ignore[override]
    # Basic fail-safe; in production use structured logging.
    log.error("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.on_event("startup")
async def start_worker() -> None:
    async def worker_loop() -> None:
        while True:
            await job_service.process_next_job()
            await anyio.sleep(0.05)

    # fire-and-forget background worker without blocking startup
    asyncio.create_task(worker_loop())
