import uuid
from datetime import datetime
from typing import List, Optional
from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from .models import MemoryCreate, MemoryResponse, SearchQuery
from .storage import get_collection, MemoryModel, AsyncSessionLocal
from .security import SecurityManager
from .config import get_settings
from .celery_app import celery_app

class MemoryManager:
    def __init__(self):
        self.settings = get_settings()
        # Model is only needed in the worker, but we keep it here for now if we run in same process
        # Ideally, we should lazy load it or only load it in the worker task.
        self.collection = get_collection()
        self.security = SecurityManager()

    async def enqueue_memory(self, memory: MemoryCreate) -> str:
        """
        Async entry point: Pushes task to Celery and returns a Task ID.
        """
        task = process_memory_task.delay(memory.model_dump())
        return task.id

    async def search_memory(self, query: SearchQuery) -> List[MemoryResponse]:
        # Search is still synchronous in terms of logic (needs embedding), 
        # but we should make DB access async.
        # For high scale, we might want a separate "Search Service" that scales independently.
        # For now, we generate embedding here (CPU bound) and query Chroma/DB.
        
        # Lazy load model here to avoid loading it in API process if possible, 
        # OR assume API has it loaded for read-path latency.
        model = SentenceTransformer(self.settings.EMBEDDING_MODEL)
        query_embedding = model.encode(query.query).tolist()
        
        where_filter = {}
        if query.session_id:
            where_filter["session_id"] = query.session_id
        if query.user_id:
            where_filter["user_id"] = query.user_id
            
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=query.limit,
            where=where_filter if where_filter else None
        )
        
        memories = []
        if results['ids'] and results['ids'][0]:
            ids = results['ids'][0]
            distances = results['distances'][0] if results['distances'] else []
            
            async with AsyncSessionLocal() as db:
                for i, mem_id in enumerate(ids):
                    result = await db.execute(select(MemoryModel).filter(MemoryModel.id == mem_id))
                    db_mem = result.scalars().first()
                    
                    if db_mem:
                        memories.append(MemoryResponse(
                            id=db_mem.id,
                            text=db_mem.text,
                            session_id=db_mem.session_id,
                            user_id=db_mem.user_id,
                            created_at=db_mem.created_at,
                            metadata=db_mem.metadata_json or {},
                            distance=distances[i] if distances else None
                        ))
                
        return memories

    async def get_history(self, session_id: str, limit: int = 100) -> List[MemoryResponse]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(MemoryModel)
                .filter(MemoryModel.session_id == session_id)
                .order_by(MemoryModel.created_at.desc())
                .limit(limit)
            )
            db_mems = result.scalars().all()
            
            return [
                MemoryResponse(
                    id=m.id,
                    text=m.text,
                    session_id=m.session_id,
                    user_id=m.user_id,
                    created_at=m.created_at,
                    metadata=m.metadata_json or {}
                ) for m in db_mems
            ]

# Celery Task
@celery_app.task
def process_memory_task(memory_dict: dict):
    """
    Background worker task:
    1. Scrub PII
    2. Generate Embedding
    3. Store in Chroma
    4. Store in Postgres
    """
    # Re-instantiate dependencies inside the worker process
    settings = get_settings()
    security = SecurityManager()
    model = SentenceTransformer(settings.EMBEDDING_MODEL)
    collection = get_collection()
    
    # Parse input
    memory = MemoryCreate(**memory_dict)
    
    # 1. Scrub PII
    if settings.ENABLE_PII_REDACTION:
        clean_text = security.scrub_pii(memory.text)
    else:
        clean_text = memory.text
    
    # Use provided ID or generate new one
    memory_id = memory.id if memory.id else str(uuid.uuid4())
    
    # 2. Generate Embedding
    embedding = model.encode(clean_text).tolist()
    
    # 3. Store in ChromaDB (Upsert)
    # Chroma's .add() might error if ID exists depending on version, .upsert() is safer if available
    # or we can just use .upsert() which is standard in newer Chroma versions.
    try:
        collection.upsert(
            documents=[clean_text],
            embeddings=[embedding],
            metadatas=[{"session_id": memory.session_id, "user_id": memory.user_id or ""}],
            ids=[memory_id]
        )
    except AttributeError:
        # Fallback for older versions if upsert not present (though it should be)
        # For now assuming upsert exists as per recent Chroma versions
        collection.add(
            documents=[clean_text],
            embeddings=[embedding],
            metadatas=[{"session_id": memory.session_id, "user_id": memory.user_id or ""}],
            ids=[memory_id]
        )

    # 4. Store in Postgres (Sync for Celery)
    # We need a sync engine for Celery since it's running in a sync worker usually, 
    # or we can use async_to_sync. Let's use a separate sync session for simplicity in the worker.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    # Convert async url to sync for worker
    sync_db_url = settings.DB_URL.replace("+asyncpg", "").replace("+aiosqlite", "")
    engine = create_engine(sync_db_url)
    SessionSync = sessionmaker(bind=engine)
    
    db = SessionSync()
    try:
        # Check if exists
        existing_mem = db.query(MemoryModel).filter(MemoryModel.id == memory_id).first()
        if existing_mem:
            # Update
            existing_mem.text = clean_text
            existing_mem.metadata_json = memory.metadata
            # session_id/user_id usually don't change for same memory ID but we can update them too
            existing_mem.session_id = memory.session_id
            existing_mem.user_id = memory.user_id
        else:
            # Insert
            db_memory = MemoryModel(
                id=memory_id,
                session_id=memory.session_id,
                user_id=memory.user_id,
                text=clean_text,
                created_at=datetime.utcnow(),
                metadata_json=memory.metadata
            )
            db.add(db_memory)
        
        db.commit()
    finally:
        db.close()
    
    return memory_id
