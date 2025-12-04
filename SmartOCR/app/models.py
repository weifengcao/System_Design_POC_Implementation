from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


class BoundingBox(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class Block(BaseModel):
    id: str
    page_number: int = Field(ge=1)
    bbox: BoundingBox
    type: Literal["paragraph", "table", "kv"] = "paragraph"
    text: str
    confidence: float = Field(ge=0, le=1)
    reading_order: int


class FieldEntry(BaseModel):
    name: str
    value: str
    bbox: Optional[BoundingBox] = None
    confidence: float = Field(ge=0, le=1)
    validator_status: Literal["passed", "failed", "skipped"] = "skipped"


class OCRResult(BaseModel):
    job_id: str
    source_uri: str
    blocks: List[Block]
    fields: List[FieldEntry]
    confidence: float = Field(ge=0, le=1)


class SyncExtractRequest(BaseModel):
    source_url: HttpUrl


class AsyncJobRequest(BaseModel):
    source_url: HttpUrl
    external_id: Optional[str] = None
    webhook_url: Optional[HttpUrl] = None
    doc_type: str = "generic"
    tenant_id: Optional[str] = None


class JobCreated(BaseModel):
    job_id: str
    status: Literal["queued", "completed"]
    doc_type: Optional[str] = None


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "in_progress", "completed", "failed"]
    result: Optional[OCRResult] = None
    error: Optional[str] = None
    doc_type: Optional[str] = None


class ReviewUpdate(BaseModel):
    fields: List[FieldEntry]
