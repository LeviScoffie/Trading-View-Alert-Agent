FROM python:3.11-slim

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install dependencies first for Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment defaults
ENV HOST=0.0.0.0
ENV PORT=8004
ENV LOG_LEVEL=INFO
ENV WEBHOOK_RECEIVER_URL=http://webhook-receiver:8000
ENV EMAIL_NOTIFIER_URL=http://email-notifier:8001
ENV SCHEDULER_URL=http://scheduler:8003
ENV CONFIDENCE_THRESHOLD=0.75
ENV REQUEST_TIMEOUT_SECONDS=10
ENV MAX_RETRIES=3

EXPOSE 8004

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8004/health || exit 1

CMD ["python", "integration_service.py"]
