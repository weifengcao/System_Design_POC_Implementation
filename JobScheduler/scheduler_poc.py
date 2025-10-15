"""Minimal Flask app for the scheduler proof of concept."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Event, Lock, Thread
from typing import Any, Dict
from uuid import uuid4
from urllib import request as urlrequest
from urllib.error import URLError

from flask import Flask, jsonify, request


@dataclass
class SchedulerState:
    """Holds job metadata and synchronization primitives for the dispatcher."""

    jobs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    lock: Lock = field(default_factory=Lock)
    wake_event: Event = field(default_factory=Event)


def parse_execution_time(value: str) -> datetime:
    """Return a timezone-aware UTC datetime parsed from ISO-8601 input."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:  # user provided invalid timestamp
        raise ValueError("Invalid execution_time_utc format") from exc
    if parsed.tzinfo is None:
        raise ValueError("execution_time_utc must include a timezone")
    return parsed.astimezone(timezone.utc)


def serialize_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """Remove internal-only fields when returning job metadata."""
    return {k: v for k, v in job.items() if not k.startswith("_")}


def dispatcher_loop(state: SchedulerState) -> None:
    """Background worker that executes due jobs."""
    while True:
        due_job_ids: list[str] = []
        next_wake: datetime | None = None
        now = datetime.now(timezone.utc)

        with state.lock:
            for job_id, job in state.jobs.items():
                if job["status"] != "scheduled":
                    continue
                execution_time: datetime = job["_execution_dt"]
                if execution_time <= now:
                    due_job_ids.append(job_id)
                else:
                    if next_wake is None or execution_time < next_wake:
                        next_wake = execution_time

        for job_id in due_job_ids:
            run_job(job_id, state)

        timeout = None
        if next_wake is not None:
            timeout = max(0.0, (next_wake - datetime.now(timezone.utc)).total_seconds())

        # Sleep briefly to avoid tight loop when no jobs exist.
        if timeout is None:
            timeout = 1.0

        state.wake_event.wait(timeout=timeout)
        state.wake_event.clear()


def run_job(job_id: str, state: SchedulerState) -> None:
    """Execute a single job and update its stored status."""
    with state.lock:
        job = state.jobs.get(job_id)
        if job is None:
            return
        job["status"] = "running"

    task = job["task"]
    task_type = task.get("type")

    if task_type == "http_callback":
        result = execute_http_callback(task)
    else:
        result = {
            "status": "failed",
            "error": f"Unsupported task type: {task_type}",
        }

    with state.lock:
        job = state.jobs.get(job_id)
        if job is None:
            return
        job["result"] = result
        job["status"] = "completed" if result.get("status") == "success" else "failed"


def execute_http_callback(task: Dict[str, Any]) -> Dict[str, Any]:
    """Trigger a simple HTTP callback defined in the job payload."""
    method = task.get("method", "GET").upper()
    url = task.get("url")
    body = task.get("body")

    if method not in {"GET", "POST"}:
        return {"status": "failed", "error": f"Unsupported HTTP method: {method}"}
    if not url:
        return {"status": "failed", "error": "Missing callback URL"}

    data_bytes = None
    if body is not None:
        import json

        try:
            data_bytes = json.dumps(body).encode("utf-8")
        except (TypeError, ValueError) as exc:
            return {"status": "failed", "error": f"Invalid JSON body: {exc}"}

    req = urlrequest.Request(url, data=data_bytes, method=method)
    if data_bytes is not None:
        req.add_header("Content-Type", "application/json")

    try:
        with urlrequest.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            return {"status": "success", "status_code": status_code}
    except URLError as exc:
        return {"status": "failed", "error": str(exc)}


def boot_dispatcher(state: SchedulerState) -> None:
    """Start the dispatcher thread only once."""
    thread = Thread(target=dispatcher_loop, args=(state,), name="job-dispatcher", daemon=True)
    thread.start()


def create_app() -> Flask:
    """Application factory used by Flask's CLI."""
    app = Flask(__name__)
    state = SchedulerState()
    app.config["SCHEDULER_STATE"] = state
    boot_dispatcher(state)

    @app.get("/")
    def health_check() -> tuple[dict[str, str], int]:
        # Basic endpoint so Flask's auto-discovery can validate the app exists.
        return jsonify(status="ok"), 200

    @app.post("/v1/jobs")
    def create_job() -> tuple[Any, int]:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="Invalid JSON payload"), 400

        try:
            job_type = payload["job_type"]
            execution_details = payload["execution_details"]
            task = payload["task"]
        except KeyError as exc:
            return jsonify(error=f"Missing required field: {exc.args[0]}"), 400

        execution_time_raw = execution_details.get("execution_time_utc")
        if not isinstance(execution_time_raw, str):
            return jsonify(error="execution_time_utc must be provided as a string"), 400

        try:
            execution_dt = parse_execution_time(execution_time_raw)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

        job_id = str(uuid4())
        job_record = {
            "id": job_id,
            "job_type": job_type,
            "execution_details": execution_details,
            "task": task,
            "status": "scheduled",
            "result": None,
            "_execution_dt": execution_dt,
        }

        with state.lock:
            state.jobs[job_id] = job_record
            state.wake_event.set()

        return jsonify(serialize_job(job_record)), 201

    @app.get("/v1/jobs/<job_id>")
    def get_job(job_id: str) -> tuple[Any, int]:
        with state.lock:
            job = state.jobs.get(job_id)
            if job is None:
                return jsonify(error="Job not found"), 404
            return jsonify(serialize_job(job)), 200

    @app.get("/v1/jobs")
    def list_jobs() -> tuple[Any, int]:
        with state.lock:
            serialized = [serialize_job(job) for job in state.jobs.values()]
        return jsonify(jobs=serialized), 200

    return app


# Expose a module-level `app` so `flask --app scheduler_poc run` works too.
app = create_app()
