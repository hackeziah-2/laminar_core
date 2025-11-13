# Example notification service. In production, implement email/SMS/push sending.
async def notify_flight_created(flight):
    # enqueue task or call external service
    return True
