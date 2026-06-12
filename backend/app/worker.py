from celery import Celery
import os
redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
celery_app = Celery("worker", broker=redis_url, backend=redis_url)
# Scheduled jobs / task timestamps follow Philippine Standard Time
celery_app.conf.timezone = "Asia/Manila"
celery_app.conf.enable_utc = False
# tasks can be created under app.tasks
