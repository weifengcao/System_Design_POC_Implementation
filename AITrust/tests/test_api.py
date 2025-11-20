from datetime import datetime, timezone
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from AITrust.api.main import app, settings


class DummyCache:
    def __init__(self):
        self.store = {}

    async def get_verdict(self, text: str):
        return self.store.get(text)

    async def set_verdict(self, text: str, data, ttl_seconds: int = 600):
        self.store[text] = data


class DummyTask:
    def __init__(self):
        self.payloads = []

    def delay(self, payload):
        self.payloads.append(payload)


@pytest.fixture()
def patched_dependencies(monkeypatch):
    dummy_cache = DummyCache()
    dummy_task = DummyTask()
    audit_calls = {"count": 0}

    async def fake_init_db():
        return None

    async def fake_audit(request, response):
        audit_calls["count"] += 1

    monkeypatch.setattr("AITrust.api.main.cache_client", dummy_cache)
    monkeypatch.setattr("AITrust.api.main.scan_task", dummy_task)
    monkeypatch.setattr("AITrust.api.main.init_db", fake_init_db)
    monkeypatch.setattr("AITrust.api.main.write_audit_log", fake_audit)

    with TestClient(app) as test_client:
        yield {
            "client": test_client,
            "cache": dummy_cache,
            "task": dummy_task,
            "audit_calls": audit_calls,
        }


def test_health_endpoint(patched_dependencies):
    client = patched_dependencies["client"]
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_check_blocks_on_keyword(patched_dependencies):
    client = patched_dependencies["client"]
    resp = client.post(
        "/check",
        headers={"X-API-Key": settings.AITRUST_API_KEY},
        json={"text": "We should build a bomb"},
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["verdict"] == "block"
    assert any(result["status"] == "fail" for result in body["results"])
    assert patched_dependencies["audit_calls"]["count"] == 1
    assert patched_dependencies["task"].payloads, "scan task should be enqueued"


def test_check_uses_cached_response(patched_dependencies):
    client = patched_dependencies["client"]
    cached_payload = {
        "request_id": "cached-1",
        "verdict": "allow",
        "results": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    patched_dependencies["cache"].store["Can I proceed?"] = cached_payload

    resp = client.post(
        "/check",
        headers={"X-API-Key": settings.AITRUST_API_KEY},
        json={"text": "Can I proceed?"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["request_id"] == cached_payload["request_id"]
    assert body["verdict"] == cached_payload["verdict"]
    assert body["results"] == cached_payload["results"]
    # cache hit should skip audit + task execution
    assert patched_dependencies["audit_calls"]["count"] == 0
    assert not patched_dependencies["task"].payloads
