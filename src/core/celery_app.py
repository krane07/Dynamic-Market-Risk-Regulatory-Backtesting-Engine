from celery import Celery
from src.core.config import settings

# Initialize the Celery app
celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['src.workers.task']
)

# Configuration tuning for Production Security
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    # set a time limit so infinite loops don't lock workers
    task_time_limit=300  
)