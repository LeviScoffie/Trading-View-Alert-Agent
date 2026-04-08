# Email Notifier Dockerfile
# TradingView Alert Agent - Scheduled Email Reports

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY config.py .
COPY templates.py .
COPY report_generator.py .
COPY email_notifier.py .

# Create data directory
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Default command - run FastAPI via uvicorn (scheduler triggers reports via HTTP)
CMD ["uvicorn", "email_notifier:app", "--host", "0.0.0.0", "--port", "8001"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1
