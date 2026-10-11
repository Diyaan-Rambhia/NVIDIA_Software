FROM python:3.13-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install build dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and README.md for dependency installation
COPY pyproject.toml README.md ./

# Install python dependencies
RUN pip install --no-cache-dir .

# Copy application source code and configuration
COPY backend ./backend
COPY config ./config
COPY Makefile ./

# Expose FastAPI application port
EXPOSE 8000

# Run uvicorn via create_app factory
CMD ["uvicorn", "backend.app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
