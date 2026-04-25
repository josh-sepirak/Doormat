# Multi-stage build: uv builder + runtime
# Stage 1: Builder
FROM python:3.13-slim AS builder

# Install uv
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

WORKDIR /build

# Copy lock file and project files
COPY uv.lock .
COPY pyproject.toml .
COPY src/backend ./src/backend

# Install dependencies with uv
RUN uv pip install --no-cache -r <(uv pip compile pyproject.toml) --target /install

# Stage 2: Runtime
FROM python:3.13-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local/lib/python3.13/site-packages

# Copy application code
COPY src/backend ./src/backend
COPY alembic ./alembic
COPY alembic.ini .

# Set Python path
ENV PYTHONPATH=/app/src/backend:$PYTHONPATH

# Create non-root user
RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5)"

# Run the application
CMD ["python", "-m", "uvicorn", "doormat.main:app", "--host", "0.0.0.0", "--port", "8000"]
