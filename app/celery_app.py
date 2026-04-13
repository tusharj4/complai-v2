from celery import Celery, Task
from kombu import Exchange, Queue
from app.config import settings


class BaseTask(Task):
    """Base task with automatic retry and exponential backoff."""
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True


celery_app = Celery(
    "complai",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL,
)

# Dead letter queue
dlq_exchange = Exchange("dlq", type="direct")

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 min hard limit
    task_soft_time_limit=25 * 60,  # 25 min soft limit
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_queues=(
        Queue("default"),
        Queue("scraping", routing_key="scraping"),
        Queue("extraction", routing_key="extraction"),
        Queue("classification", routing_key="classification"),
        Queue("dlq", exchange=dlq_exchange, routing_key="dlq"),
    ),
    task_routes={
        "app.tasks.orchestration.*": {"queue": "default"},
        "app.tasks.workers.extract_and_classify": {"queue": "extraction"},
        "app.tasks.workers.classify_document": {"queue": "classification"},
        "app.tasks.workers.scrape_portal": {"queue": "scraping"},
    },
)
