from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime
import uuid

class CheckRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None

class CheckResult(BaseModel):
    check_name: str
    status: str # "pass", "fail", "warn"
    score: float
    metadata: Optional[dict] = None

class TrustResponse(BaseModel):
    request_id: str
    verdict: str # "allow", "block"
    results: List[CheckResult]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AuditLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str
    timestamp: datetime
    input_text: str
    verdict: str
    results_json: dict
