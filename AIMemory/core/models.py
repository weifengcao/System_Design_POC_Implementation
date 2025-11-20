from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

class MemoryBase(BaseModel):
    text: str
    session_id: str
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class MemoryCreate(MemoryBase):
    id: Optional[str] = None

class MemoryResponse(MemoryBase):
    id: str
    created_at: datetime
    distance: Optional[float] = None

class SearchQuery(BaseModel):
    query: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    limit: int = 5
    threshold: float = 0.5
