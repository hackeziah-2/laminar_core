FROM python:3.11-slim
WORKDIR /app
COPY ./ /app
ENV PYTHONPATH=/app
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
# "celery", "--broker=redis://redis:6379/0", "flower", 