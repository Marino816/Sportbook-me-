"""
Shared Celery application for all SB ME background tasks.

Start with: celery -A worker.celery worker --loglevel=info
"""
import os
from celery import Celery

REDIS_BROKER = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
celery_app = Celery("sbme_worker", broker=REDIS_BROKER, backend=REDIS_BROKER)
# NOTE: no custom task_routes — all tasks use the default "celery" queue,
# matching the worker start command "celery -A worker.tasks worker".
