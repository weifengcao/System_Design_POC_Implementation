"""Minimal Flask app for the scheduler proof of concept."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Event, Lock, Thread
from typing import Any, Dict, Iterable, Set
from uuid import uuid4
from urllib import request as urlrequest
from urllib.error import URLError

from flask import Flask, jsonify, request


class CronExpressionError(ValueError):
    """Raised when a cron expression is invalid."""


def _parse_cron_field(field: str, minimum: int, maximum: int, *, wrap_sunday: bool = False) -> Set[int] | None:
    """Parse cron field or detect wildcard."""

    def expand_range(start: int, end: int, step: int) -> Iterable[int]:
        if start > end:
            raise CronExpressionError(f"Invalid range {start}-{end}")
        return range(start, end + 1, step)

    field = field.strip()
    if field == "*":
        return None

    values: Set[int] = set()
    for segment in field.split(","):
        segment = segment.strip()
        if not segment:
            raise CronExpressionError("Empty cron segment")

        step = 1
        if "/" in segment:
            base, step_part = segment.split("/", 1)
            if not step_part:
                raise CronExpressionError("Missing step value")
            try:
                step = int(step_part)
            except ValueError as exc:
                raise CronExpressionError(f"Invalid step value: {segment}") from exc
            if step <= 0:
                raise CronExpressionError("Step must be positive")
            segment = base or "*"

        if segment == "*":
            values.update(range(minimum, maximum + 1, step))
            continue

        if "-" in segment:
            start_str, end_str = segment.split("-", 1)
            try:
                start_val = int(start_str)
                end_val = int(end_str)
            except ValueError as exc:
                raise CronExpressionError(f"Invalid range value: {segment}") from exc
            if wrap_sunday:
                if start_val == 7:
                    start_val = 0
                if end_val == 7:
                    end_val = 0
            for value in expand_range(start_val, end_val, step):
                if value < minimum or value > maximum:
                    raise CronExpressionError(f"Value {value} out of bounds")
                values.add(value)
            continue

        try:
            value = int(segment)
        except ValueError as exc:
            raise CronExpressionError(f"Invalid field value: {segment}") from exc
        if wrap_sunday and value == 7:
            value = 0
        if value < minimum or value > maximum:
            raise CronExpressionError(f"Value {value} out of bounds")
        values.add(value)

    return values


class CronSchedule:
    """Compute next run times for simple cron expressions."""

    def __init__(self, expression: str):
        fields = expression.split()
        if len(fields) != 5:
            raise CronExpressionError("Cron expression must have five fields")

        self.minutes = _parse_cron_field(fields[0], 0, 59)
        self.hours = _parse_cron_field(fields[1], 0, 23)
        self.days_of_month = _parse_cron_field(fields[2], 1, 31)
        self.months = _parse_cron_field(fields[3], 1, 12)
        self.days_of_week = _parse_cron_field(fields[4], 0, 6, wrap_sunday=True)

    def _matches(self, candidate: datetime) -> bool:
        if candidate.tzinfo is None:
            raise ValueError("candidate must be timezone-aware")

        if self.months is not None and candidate.month not in self.months:
            return False
        if self.hours is not None and candidate.hour not in self.hours:
            return False
        if self.minutes is not None and candidate.minute not in self.minutes:
            return False

        dom_match = self.days_of_month is None or candidate.day in self.days_of_month
        dow_value = (candidate.weekday() + 1) % 7  # convert Monday=0 to Sunday=0
        dow_match = self.days_of_week is None or dow_value in self.days_of_week

        if self.days_of_month is not None and self.days_of_week is not None:
            return dom_match or dow_match
        return dom_match and dow_match

    def next_run(self, reference: datetime, *, include_reference: bool) -> datetime:
        if reference.tzinfo is None:
            raise ValueError("reference must be timezone-aware")

        ref_utc = reference.astimezone(timezone.utc)
        candidate = ref_utc.replace(second=0, microsecond=0)
        if include_reference:
            if candidate < ref_utc:
                candidate += timedelta(minutes=1)
        else:
            if candidate <= ref_utc:
                candidate += timedelta(minutes=1)

        search_deadline = candidate + timedelta(days=366)
        while candidate <= search_deadline:
            if self._matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)

        raise CronExpressionError("Unable to find next run within one year")


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
        job["last_run_started_at"] = datetime.now(timezone.utc).isoformat()

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
        job["last_run_completed_at"] = datetime.now(timezone.utc).isoformat()
        job.pop("error", None)

        if job["job_type"] == "cron":
            cron_schedule: CronSchedule | None = job.get("_cron_schedule")
            if cron_schedule is None:
                job["status"] = "failed"
                job["next_run_time_utc"] = None
                job["error"] = "Missing cron schedule metadata"
                return
            try:
                next_run = cron_schedule.next_run(job["_execution_dt"], include_reference=False)
            except CronExpressionError as exc:
                job["status"] = "failed"
                job["next_run_time_utc"] = None
                job["error"] = f"Failed to compute next cron occurrence: {exc}"
            else:
                job["_execution_dt"] = next_run
                job["next_run_time_utc"] = next_run.isoformat()
                job["status"] = "scheduled"
                state.wake_event.set()
        else:
            job["status"] = "completed" if result.get("status") == "success" else "failed"
            job["next_run_time_utc"] = None


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
        if job_type not in {"ad_hoc", "cron"}:
            return jsonify(error="Unsupported job_type"), 400

        job_id = str(uuid4())
        job_record: Dict[str, Any] = {
            "id": job_id,
            "job_type": job_type,
            "execution_details": execution_details,
            "task": task,
            "status": "scheduled",
            "result": None,
            "next_run_time_utc": None,
            "last_run_started_at": None,
            "last_run_completed_at": None,
        }

        try:
            if job_type == "ad_hoc":
                execution_time_raw = execution_details.get("execution_time_utc")
                if not isinstance(execution_time_raw, str):
                    return jsonify(error="execution_time_utc must be provided as a string"), 400
                execution_dt = parse_execution_time(execution_time_raw)
            else:
                cron_expression = execution_details.get("cron_expression")
                if not isinstance(cron_expression, str):
                    return jsonify(error="cron_expression must be provided as a string"), 400

                start_time_raw = execution_details.get("start_time_utc")
                if start_time_raw is None:
                    start_dt = datetime.now(timezone.utc)
                elif isinstance(start_time_raw, str):
                    try:
                        start_dt = parse_execution_time(start_time_raw)
                    except ValueError as exc:
                        return jsonify(error=str(exc)), 400
                else:
                    return jsonify(error="start_time_utc must be provided as a string"), 400

                try:
                    cron_schedule = CronSchedule(cron_expression)
                    execution_dt = cron_schedule.next_run(start_dt, include_reference=True)
                except CronExpressionError as exc:
                    return jsonify(error=f"Invalid cron expression: {exc}"), 400
                job_record["_cron_schedule"] = cron_schedule
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

        job_record["_execution_dt"] = execution_dt
        job_record["next_run_time_utc"] = execution_dt.isoformat()

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
