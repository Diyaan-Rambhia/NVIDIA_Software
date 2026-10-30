FROM python:3.13-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and README.md for dependency installation
COPY pyproject.toml README.md ./

# Install python dependencies
RUN pip install --no-cache-dir .

# Copy application source code, configuration, frontend assets, and precomputed data
# Strict policy: .env is NEVER copied into the image
COPY backend ./backend
COPY config ./config
COPY frontend ./frontend
COPY data ./data
COPY Makefile ./

# Expose default application port
EXPOSE 8000

# Run uvicorn reading PORT dynamically from environment
CMD ["sh", "-c", "uvicorn backend.app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
