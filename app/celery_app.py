from celery import Celery
from app.config import get_settings

settings = get_settings()
celery_app = Celery("test_api", broker=settings.redis_url, backend=settings.redis_url, include=["app.tasks"])
celery_app.conf.update(task_track_started=True, task_serializer="json", result_serializer="json", accept_content=["json"], broker_connection_retry_on_startup=True, task_acks_late=True, worker_prefetch_multiplier=1)
