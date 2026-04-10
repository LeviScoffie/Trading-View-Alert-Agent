# Analysis Engine Dockerfile
# Lightweight container for trading analysis

FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY *.py .

# Create data directory
RUN mkdir -p /app/data

# Environment defaults
ENV HOST=0.0.0.0
ENV PORT=8001
ENV LOG_LEVEL=INFO
ENV OHLCV_DB_PATH=/app/data/ohlcv.db

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8001/health || exit 1

CMD ["python", "api.py"]
