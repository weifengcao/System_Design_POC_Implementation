import chromadb
from chromadb.config import Settings as ChromaSettings
from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from datetime import datetime
import os
from .config import get_settings

settings = get_settings()

# Database Setup
Base = declarative_base()

class MemoryModel(Base):
    __tablename__ = "memories"
    id = Column(String, primary_key=True)
    session_id = Column(String, index=True)
    user_id = Column(String, index=True, nullable=True)
    text = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata_json = Column(JSON)

# Handle SQLite vs Postgres for Async
db_url = settings.DB_URL
connect_args = {}

if db_url.startswith("sqlite"):
    # Async SQLite requires aiosqlite
    db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")
else:
    # Postgres SSL
    if settings.DB_SSL_MODE != "disable":
        connect_args = {"ssl": settings.DB_SSL_MODE}

engine = create_async_engine(db_url, echo=False, connect_args=connect_args)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# ChromaDB Setup (Client)
# In distributed mode, we use HttpClient. In local, we might fallback or just assume server is running.
chroma_client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
collection = chroma_client.get_or_create_collection(name="memories")

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

def get_collection():
    return collection
