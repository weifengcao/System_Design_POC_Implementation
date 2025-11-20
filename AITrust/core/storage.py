from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, DateTime, JSON, Text
from .config import get_settings

settings = get_settings()

# DB Setup
connect_args = {}
if settings.DB_SSL_MODE != "disable":
    connect_args = {"ssl": settings.DB_SSL_MODE}

engine = create_async_engine(settings.DB_URL, echo=False, connect_args=connect_args)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

class AuditLogModel(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True)
    request_id = Column(String, index=True)
    timestamp = Column(DateTime)
    input_text = Column(Text) # Encrypted/Redacted in real prod
    verdict = Column(String)
    results_json = Column(JSON)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
