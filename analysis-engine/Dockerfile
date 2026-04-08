# Analysis Engine Dockerfile
# Lightweight container for trading analysis

FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY *.py .

# Create data directory
RUN mkdir -p /app/data

# Default database path
ENV DB_PATH=/app/data/ohlcv.db

# Run tests by default (override with command)
CMD ["python", "-m", "pytest", "test_patterns.py", "-v"]

# Alternative: run as module
# CMD ["python", "-c", "from analysis_engine import analyze; print(analyze('BTCUSD'))"]
