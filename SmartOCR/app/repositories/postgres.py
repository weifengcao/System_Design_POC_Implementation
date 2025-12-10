from __future__ import annotations

from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session

from . import JobRepository
from .. import storage, models
from ..sql_models import Job as JobModel


class PostgresJobRepository(JobRepository):
    def __init__(self, db: Session):
        self.db = db

    def create(self, job: storage.Job) -> None:
        job_model = JobModel(**job.dict())
        self.db.add(job_model)
        self.db.commit()

    def get(self, job_id: str) -> Optional[storage.Job]:
        job_model = self.db.query(JobModel).filter(JobModel.id == UUID(job_id)).first()
        if job_model:
            return storage.Job.from_orm(job_model)
        return None

    def list(self, limit: int = 50) -> List[storage.Job]:
        job_models = self.db.query(JobModel).limit(limit).all()
        return [storage.Job.from_orm(job) for job in job_models]

    def mark_in_progress(self, job_id: str) -> None:
        job_model = self.db.query(JobModel).filter(JobModel.id == UUID(job_id)).first()
        if job_model:
            job_model.status = "in_progress"
            self.db.commit()

    def complete(self, job_id: str, result: models.OCRResult) -> None:
        job_model = self.db.query(JobModel).filter(JobModel.id == UUID(job_id)).first()
        if job_model:
            job_model.status = "completed"
            job_model.result = result.dict()
            self.db.commit()

    def fail(self, job_id: str, error: str) -> None:
        job_model = self.db.query(JobModel).filter(JobModel.id == UUID(job_id)).first()
        if job_model:
            job_model.status = "failed"
            job_model.error = error
            self.db.commit()
