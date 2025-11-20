from celery import Celery
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
