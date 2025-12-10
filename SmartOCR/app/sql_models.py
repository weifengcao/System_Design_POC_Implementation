from sqlalchemy import create_engine, Column, String, JSON, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import uuid

from .config import settings

Base = declarative_base()

class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String, index=True)
    source_uri = Column(String, nullable=False)
    status = Column(String, nullable=False, default="queued")
    webhook_url = Column(String)
    doc_type = Column(String, default="generic")
    tenant_id = Column(String, index=True)
    result = Column(JSON)
    error = Column(String)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
