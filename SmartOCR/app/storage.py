from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID, uuid4

from . import models


class Job(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    external_id: Optional[str] = None
    source_uri: str
    status: str = "queued"
    doc_type: str = "generic"
    webhook_url: Optional[str] = None
    result: Optional[models.OCRResult] = None
    error: Optional[str] = None
    tenant_id: Optional[str] = None

    class Config:
        orm_mode = True
