from types import SimpleNamespace

try:
    from celery import Celery
except ModuleNotFoundError:  # pragma: no cover - fallback for local dev/tests
    class Celery:  # type: ignore
        def __init__(self, *args, **kwargs):
            self.conf = SimpleNamespace(task_routes={})

        def task(self, *dargs, **dkwargs):
            def decorator(func):
                return func
            return decorator

        def send_task(self, *args, **kwargs):  # compatibility no-op
            return None

from .config import get_settings

settings = get_settings()

celery_app = Celery(
    "aitrust",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.task_routes = {
    "core.scanner.scan_task": "scanner-queue"
}
