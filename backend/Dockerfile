# FROM python:3.11-slim
# WORKDIR /app
# COPY ./ /app
# ENV PYTHONPATH=/app
# RUN apt-get update \
#     && apt-get install -y --no-install-recommends \
#         build-essential \
#         libpq-dev \
#     && apt-get clean \
#     && rm -rf /var/lib/apt/lists/*

# RUN pip install --upgrade pip
# RUN pip install --no-cache-dir -r requirements.txt
# ENV PYTHONUNBUFFERED=1
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
# # "celery", "--broker=redis://redis:6379/0", "flower", 


FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

# Install system dependencies for psycopg2, pycairo/reportlab
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libcairo2-dev \
    pkg-config \
    python3-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
