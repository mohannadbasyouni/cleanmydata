FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# System deps (pandas wheels sometimes need gcc)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy metadata first for better layer caching
COPY pyproject.toml README.md ./
COPY cleanmydata ./cleanmydata

# Install Python deps WITH GCS enabled
RUN pip install --upgrade pip \
    && pip install --no-cache-dir ".[api,gcs]"

EXPOSE 8080

CMD ["sh", "-c", "uvicorn cleanmydata.api:app --host 0.0.0.0 --port ${PORT:-8080}"]
