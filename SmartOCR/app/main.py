from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, Header, Depends
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import models, storage, config, service, pipeline, ingestion
from .repositories import InMemoryJobRepository
from .queue_backends import AsyncQueueBackend, RabbitMQBackend, AsyncInMemoryQueueBackend


# ---- App Setup ----
app = FastAPI(title="SmartOCR", version="0.1.0")
log = logging.getLogger("smartocr")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- DI Setup ----
def get_settings() -> config.Settings:
    return config.settings


async def get_queue() -> AsyncQueueBackend:
    if get_settings().USE_RABBITMQ:
        q = RabbitMQBackend(amqp_url=get_settings().AMQP_URL)
        await q.connect()
        yield q
        await q.disconnect()
    else:
        yield AsyncInMemoryQueueBackend()


from .repositories import JobRepository, PostgresJobRepository, InMemoryJobRepository
from .database import get_db, SessionLocal


def get_job_repository(db: Session = Depends(get_db)) -> JobRepository:
    if get_settings().USE_POSTGRES:
        return PostgresJobRepository(db)
    else:
        return InMemoryJobRepository()


from .object_store import MinioDocumentStore


def get_document_store() -> MinioDocumentStore:
    return MinioDocumentStore()


def get_downloader() -> service.Downloader:
    return service.Downloader()

def get_job_service(
    docs: MinioDocumentStore = Depends(get_document_store),
    jobs: JobRepository = Depends(get_job_repository),
    queue: AsyncQueueBackend = Depends(get_queue),
    downloader: service.Downloader = Depends(get_downloader),
) -> service.JobService:
    return service.JobService(docs=docs, jobs=jobs, queue=queue, downloader=downloader)


def get_api_key(x_api_key: str = Header(None)) -> str:
    if get_settings().API_KEY and x_api_key != get_settings().API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")
    return x_api_key


# ---- Worker Lifecycle ----
worker_stop_event = asyncio.Event()


@app.on_event("startup")
async def startup():
    # In a real app, you might not want to run the worker in the same process as the API
    if get_settings().RUN_WORKER:
        asyncio.create_task(run_worker())


async def run_worker():
    # This is a bit of a hack to get a JobService instance for the worker
    # In a real app, the worker would be a separate process with its own DI setup
    if get_settings().USE_RABBITMQ:
        q = RabbitMQBackend(amqp_url=get_settings().AMQP_URL)
        await q.connect()
    else:
        q = AsyncInMemoryQueueBackend()

    if get_settings().USE_POSTGRES:
        db = SessionLocal()
        job_repo = PostgresJobRepository(db)
    else:
        job_repo = InMemoryJobRepository()

    job_service = service.JobService(
        docs=get_document_store(),
        jobs=job_repo,
        queue=q,
        downloader=get_downloader(),
    )
    await job_service.worker(worker_stop_event)

    if get_settings().USE_RABBITMQ:
        await q.disconnect()
    if get_settings().USE_POSTGRES:
        db.close()


@app.on_event("shutdown")
async def shutdown():
    worker_stop_event.set()


# ---- API Endpoints ----
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ocr/extract", response_model=models.OCRResult)
async def extract_ocr(
    file: Optional[UploadFile] = File(default=None),
    payload: Optional[models.SyncExtractRequest] = None,
    doc_type: str = "generic",
    api_key: str = Depends(get_api_key),
    downloader: service.Downloader = Depends(get_downloader),
    doc_store: MinioDocumentStore = Depends(get_document_store),
) -> models.OCRResult:
    if not file and not payload:
        raise HTTPException(status_code=400, detail="Either a file upload or a source_url is required.")

    source_uri = "upload"
    if file:
        content = await file.read()
        source_uri = file.filename or "upload"
    elif payload:
        content = await downloader.fetch_bytes(payload.source_url)
        source_uri = payload.source_url

    doc_id = "sync_doc"
    doc_store.save(doc_id, content)
    result = pipeline.run_ocr(content, doc_type=doc_type)
    result.job_id = doc_id
    result.source_uri = source_uri
    return result


@app.post("/ocr/jobs", response_model=models.JobCreated)
async def create_job(
    body: models.AsyncJobRequest,
    job_service: service.JobService = Depends(get_job_service),
    api_key: str = Depends(get_api_key),
) -> models.JobCreated:
    return await job_service.create_job(
        source_uri=body.source_url,
        external_id=body.external_id,
        webhook_url=body.webhook_url,
        doc_type=body.doc_type,
        tenant_id=body.tenant_id,
    )


@app.get("/ocr/jobs/{job_id}", response_model=models.JobStatus)
async def get_job(
    job_id: str,
    job_service: service.JobService = Depends(get_job_service),
    api_key: str = Depends(get_api_key),
) -> models.JobStatus:
    job = await job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return models.JobStatus.from_orm(job)


@app.get("/ocr/jobs", response_model=list[models.JobStatus])
async def list_jobs(
    limit: int = 50,
    job_service: service.JobService = Depends(get_job_service),
    api_key: str = Depends(get_api_key),
) -> list[models.JobStatus]:
    jobs = await job_service.list_jobs(limit=limit)
    return [models.JobStatus.from_orm(j) for j in jobs]


@app.patch("/ocr/jobs/{job_id}/fields", response_model=models.JobStatus)
async def review_job(
    job_id: str,
    body: models.ReviewUpdate,
    job_service: service.JobService = Depends(get_job_service),
    api_key: str = Depends(get_api_key),
) -> models.JobStatus:
    return await job_service.update_review(job_id=job_id, fields=body.fields)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    log.error("Unhandled error: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
