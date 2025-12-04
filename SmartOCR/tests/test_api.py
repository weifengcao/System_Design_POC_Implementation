import base64
import io
import time
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


client = TestClient(app)


def test_health() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_sync_extract_with_source_url() -> None:
    img = Image.new("RGB", (100, 50), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    payload = {"source_url": data_uri}
    res = client.post("/ocr/extract", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["job_id"]
    assert body["source_uri"]
    assert body["blocks"] is not None
    assert body["fields"]


def test_async_job_lifecycle() -> None:
    img = Image.new("RGB", (60, 60), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    payload = {"source_url": data_uri}
    res = client.post("/ocr/jobs", json=payload)
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    assert res.json()["doc_type"] == "generic"
    # Poll for completion (background worker loop)
    for _ in range(20):
        status_res = client.get(f"/ocr/jobs/{job_id}")
        assert status_res.status_code == 200
        status_body = status_res.json()
        if status_body["status"] == "completed":
            break
        time.sleep(0.1)
    else:
        raise AssertionError("Job did not complete in time")

    assert status_body["result"]["job_id"] == job_id
    assert status_body["result"]["fields"]
    assert status_body["doc_type"] == "generic"


def test_review_edit_updates_fields() -> None:
    img = Image.new("RGB", (80, 40), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    payload = {"source_url": data_uri}
    res = client.post("/ocr/jobs", json=payload)
    job_id = res.json()["job_id"]
    # Wait for completion
    for _ in range(20):
        status_body = client.get(f"/ocr/jobs/{job_id}").json()
        if status_body["status"] == "completed":
            break
        time.sleep(0.1)

    original_fields = status_body["result"]["fields"]
    edited_fields = original_fields.copy()
    edited_fields[0]["value"] = "UPDATED"

    patch_res = client.patch(f"/ocr/jobs/{job_id}/fields", json={"fields": edited_fields})
    assert patch_res.status_code == 200
    patched = patch_res.json()
    assert patched["result"]["fields"][0]["value"] == "UPDATED"
    assert patched["doc_type"] == "generic"
