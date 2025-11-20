import pytest
from fastapi.testclient import TestClient
from main import app
from core.memory_manager import MemoryManager
from core.models import MemoryCreate, SearchQuery
import uuid

client = TestClient(app)

# Mock MemoryManager to avoid real DB calls during unit tests if possible, 
# but for this POC we'll use the real one with a test DB path if we could, 
# or just rely on the fact that it's local. 
# For better isolation, we should probably override the DB path, but let's keep it simple for now.

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_add_and_retrieve_memory():
    session_id = str(uuid.uuid4())
    text = "The user's favorite color is blue."
    
    # Add Memory
    response = client.post("/api/v1/memory", json={
        "text": text,
        "session_id": session_id,
        "user_id": "user_123",
        "metadata": {"source": "chat"}
    })
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == text
    assert data["session_id"] == session_id
    
    # Search Memory
    search_response = client.post("/api/v1/memory/search", json={
        "query": "What is the favorite color?",
        "session_id": session_id,
        "limit": 1
    })
    assert search_response.status_code == 200
    results = search_response.json()
    assert len(results) > 0
    assert "blue" in results[0]["text"]

def test_pii_redaction():
    session_id = str(uuid.uuid4())
    text = "My email is test@example.com and phone is 123-456-7890."
    
    response = client.post("/api/v1/memory", json={
        "text": text,
        "session_id": session_id
    })
    assert response.status_code == 200
    data = response.json()
    
    assert "test@example.com" not in data["text"]
    assert "[EMAIL_REDACTED]" in data["text"]
    assert "123-456-7890" not in data["text"]
    assert "[PHONE_REDACTED]" in data["text"]

def test_session_history():
    session_id = str(uuid.uuid4())
    texts = ["Fact 1", "Fact 2", "Fact 3"]
    
    for t in texts:
        client.post("/api/v1/memory", json={"text": t, "session_id": session_id})
        
    response = client.get(f"/api/v1/sessions/{session_id}/history")
    assert response.status_code == 200
    history = response.json()
    assert len(history) == 3
