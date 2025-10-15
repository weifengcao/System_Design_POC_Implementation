## Scheduler Proof of Concept

### Goals
- Accept ad-hoc jobs via HTTP
- Persist jobs in-memory for the session
- Dispatch jobs at/after their scheduled execution time
- Execute simple HTTP callback tasks

### API Surface
- `POST /v1/jobs` — create a job. Required fields:
  - `job_type`: currently supports `ad_hoc`
  - `execution_details.execution_time_utc`: ISO-8601 UTC timestamp
  - `task`: payload describing the work (supports `http_callback`)
- `GET /v1/jobs/<job_id>` — return status/result for a specific job
- `GET /v1/jobs` — list all jobs known to the dispatcher
- `GET /` — health probe

### Dispatcher/Worker
- `SchedulerState` holds job metadata, thread lock, and wake event
- Dispatcher thread (`dispatcher_loop`) waits for due jobs, executes them, and updates status
- HTTP callback executor uses `urllib` for network requests (GET/POST)
- Jobs transition through `scheduled -> running -> completed/failed`

### Future Enhancements
- Durable storage (SQLite, Redis) for restart safety
- Retry/backoff and richer failure reporting
- Additional task types (e.g., shell commands, batch jobs)
- Observability: structured logging, metrics, dashboard
