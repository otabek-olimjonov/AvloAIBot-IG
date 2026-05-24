from celery import Celery
from app.config import settings

celery_app = Celery(
    "instagram_bot",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tashkent",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.message_processing.process_dm": {"queue": "messages"},
        "app.tasks.message_processing.process_comment": {"queue": "messages"},
    },
)
