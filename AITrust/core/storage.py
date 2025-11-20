from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, DateTime, JSON, Text

from .config import get_settings

settings = get_settings()

Base = declarative_base()
_engine = None
AsyncSessionLocal = None


def _create_engine():
    global _engine, AsyncSessionLocal
    if _engine is not None:
        return _engine

    connect_args = {}
    if settings.DB_SSL_MODE != "disable":
        connect_args = {"ssl": settings.DB_SSL_MODE}

    try:
        _engine = create_async_engine(settings.DB_URL, echo=False, connect_args=connect_args)
    except ModuleNotFoundError as exc:  # pragma: no cover - fallback for local dev/tests
        if "asyncpg" not in str(exc):
            raise
        _engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    AsyncSessionLocal = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    return _engine


def get_session_factory():
    global AsyncSessionLocal
    if AsyncSessionLocal is None:
        _create_engine()
    return AsyncSessionLocal

class AuditLogModel(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True)
    request_id = Column(String, index=True)
    timestamp = Column(DateTime)
    input_text = Column(Text) # Encrypted/Redacted in real prod
    verdict = Column(String)
    results_json = Column(JSON)

async def init_db():
    engine = _create_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
