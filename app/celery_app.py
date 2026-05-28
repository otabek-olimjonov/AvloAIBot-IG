from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "instagram_bot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.message_processing"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tashkent",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # ── RedBeat: Redis-backed scheduler (no drift, no stale schedule files) ──
    beat_scheduler="redbeat.schedulers:RedBeatScheduler",
    redbeat_redis_url=settings.redis_url,

    task_routes={
        "app.tasks.message_processing.process_dm": {"queue": "messages"},
        "app.tasks.message_processing.process_comment_dm": {"queue": "messages"},
        "app.tasks.message_processing.close_stale_conversations": {"queue": "maintenance"},
        "app.tasks.message_processing.poll_new_comments": {"queue": "maintenance"},
    },
    # Celery Beat periodic schedule
    beat_schedule={
        # Close conversations that have been idle for >24 hours — runs every hour
        "close-stale-conversations": {
            "task": "app.tasks.message_processing.close_stale_conversations",
            "schedule": crontab(minute=0),  # top of every hour
        },
        # Poll Instagram for new comments every 5 minutes
        "poll-new-comments": {
            "task": "app.tasks.message_processing.poll_new_comments",
            "schedule": 300.0,  # every 5 minutes
        },
    },
)
