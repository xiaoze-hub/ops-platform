# ops-platform API image
# Multi-stage build on python:3.11-slim
# Build context MUST be the repo root (docker-compose sets context: .)
# so root requirements.txt and platform/app are both visible.

FROM python:3.11-slim AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Root requirements.txt (psycopg binary wheels; gcc/libpq-dev for any source builds)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim AS runtime

# Runtime libpq in case psycopg loads against system libpq
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app
# Backend package only — not the whole repo
COPY platform/app /app/app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_MODULE=app.main:app \
    APP_PORT=8081

EXPOSE 8081

# Health endpoint: GET /api/v1/health
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081"]
