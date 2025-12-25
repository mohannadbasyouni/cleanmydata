FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# Install system dependencies required by pandas and FastAPI.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy metadata first for dependency caching, then source for installation.
COPY pyproject.toml README.md ./
COPY cleanmydata ./cleanmydata

# Install Python dependencies after source is available.
RUN pip install --upgrade pip \
    && pip install --no-cache-dir .[api]

EXPOSE 8080

CMD ["sh", "-c", "uvicorn cleanmydata.api:app --host 0.0.0.0 --port ${PORT:-8080}"]
