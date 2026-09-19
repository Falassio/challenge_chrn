# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/day1/src:/app/day2/src"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# utente non-root per sicurezza
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/output/plots /app/day1/data && \
    chown -R appuser:appuser /app

COPY --chown=appuser:appuser day1 /app/day1
COPY --chown=appuser:appuser day2 /app/day2
COPY --chown=appuser:appuser README.md /app/README.md

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "chiron_service.main:app", "--host", "0.0.0.0", "--port", "8000"]

