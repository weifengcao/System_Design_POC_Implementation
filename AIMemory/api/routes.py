from fastapi import APIRouter, HTTPException, Depends, Security
from typing import List, Dict
from core.models import MemoryCreate, MemoryResponse, SearchQuery
from core.memory_manager import MemoryManager
from core.auth import get_api_key

router = APIRouter()
memory_manager = MemoryManager() # Singleton-ish

@router.post("/memory", response_model=Dict[str, str], dependencies=[Depends(get_api_key)])
async def add_memory(memory: MemoryCreate):
    """
    Async endpoint: Returns a Task ID immediately.
    """
    try:
        task_id = await memory_manager.enqueue_memory(memory)
        return {"task_id": task_id, "status": "processing"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/memory/search", response_model=List[MemoryResponse], dependencies=[Depends(get_api_key)])
async def search_memory(query: SearchQuery):
    try:
        return await memory_manager.search_memory(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/history", response_model=List[MemoryResponse], dependencies=[Depends(get_api_key)])
async def get_session_history(session_id: str, limit: int = 100):
    try:
        return await memory_manager.get_history(session_id, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
