# TradingView Alert Agent Scheduler - Docker Image
# Multi-stage build for smaller production image

# =============================================================================
# BUILD STAGE
# =============================================================================
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# =============================================================================
# PRODUCTION STAGE
# =============================================================================
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:$PATH" \
    SCHEDULER_DB_PATH=/data/scheduler.db \
    SCHEDULER_LOG_LEVEL=INFO \
    SCHEDULER_API_HOST=0.0.0.0 \
    SCHEDULER_API_PORT=8003 \
    TZ=America/New_York

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    tzdata \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Create data directory
RUN mkdir -p /data

# Set working directory
WORKDIR /app

# Copy application code
COPY *.py .

# Create non-root user for security
RUN useradd -m -u 1000 scheduler && \
    chown -R scheduler:scheduler /app /data
USER scheduler

# Expose API port
EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

# Default command: run the API server
CMD ["python", "api.py"]
