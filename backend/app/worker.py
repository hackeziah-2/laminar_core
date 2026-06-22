from celery import Celery
import os
from app.core.scheduler import register_periodic_jobs

redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
celery_app = Celery("worker", broker=redis_url, backend=redis_url)
# Scheduled jobs / task timestamps follow Philippine Standard Time
celery_app.conf.timezone = "Asia/Manila"
celery_app.conf.beat_schedule_timezone = "Asia/Manila"
celery_app.conf.enable_utc = False
celery_app.conf.imports = (
    "app.tasks.advisory_notifications",
    "app.tasks.notify",
)
register_periodic_jobs(celery_app)
