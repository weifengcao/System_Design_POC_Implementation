from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections import defaultdict, deque

from fastapi.testclient import TestClient

from Twitter import api
from Twitter.prototype import TwitterService


def reset_api_state(rate_limit: int = 5) -> TestClient:
    api.service = TwitterService()
    api.API_KEYS = frozenset({"test-key"})
    api.RATE_LIMIT = rate_limit
    api.RATE_WINDOW_SECONDS = 60
    api.JWT_SECRET = None
    api._rate_counters = defaultdict(deque)
    return TestClient(api.app)


def test_missing_api_key_denied():
    client = reset_api_state()
    response = client.post("/users", json={"screen_name": "alice"})
    assert response.status_code == 401


def test_valid_key_succeeds():
    client = reset_api_state()
    headers = {"X-API-Key": "test-key"}
    response = client.post("/users", json={"screen_name": "alice"}, headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["screen_name"] == "alice"
    assert "id" in payload


def test_multiple_api_keys_supported():
    client = reset_api_state()
    api.API_KEYS = frozenset({"test-key", "alt-key"})
    headers = {"X-API-Key": "alt-key"}
    response = client.post("/users", json={"screen_name": "alt"}, headers=headers)
    assert response.status_code == 200


def test_rate_limit_enforced():
    client = reset_api_state(rate_limit=2)
    headers = {"X-API-Key": "test-key"}
    assert client.post("/users", json={"screen_name": "alice"}, headers=headers).status_code == 200
    assert client.post("/users", json={"screen_name": "bob"}, headers=headers).status_code == 200
    third = client.post("/users", json={"screen_name": "charlie"}, headers=headers)
    assert third.status_code == 429


def _make_jwt(subject: str, secret: str, exp_offset: int = 60) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": subject, "exp": int(time.time()) + exp_offset}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def test_bearer_token_authorized():
    client = reset_api_state()
    api.JWT_SECRET = "secret"
    token = _make_jwt("user-123", api.JWT_SECRET)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/users", json={"screen_name": "bearer_user"}, headers=headers)
    assert response.status_code == 200


def test_invalid_bearer_rejected():
    client = reset_api_state()
    api.JWT_SECRET = "secret"
    token = _make_jwt("user-123", api.JWT_SECRET)
    headers = {"Authorization": f"Bearer {token}tampered"}
    response = client.post("/users", json={"screen_name": "bearer_user"}, headers=headers)
    assert response.status_code == 401
