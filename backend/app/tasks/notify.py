from app.worker import celery_app
@celery_app.task
def send_notification(data):
    print("Notification task:", data)
    return True
