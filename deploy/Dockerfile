# =============================================================================
# GridWise LLM — Smart Campus Energy Optimization Service
# Production Dockerfile (Member 4 deliverable)
# =============================================================================
# Base image: python:3.11-slim
# - Slim Debian-based image, ~150 MB
# - Python 3.11 is the target version (FastAPI 0.110+, Pydantic V2, SciPy 1.11+ all stable)
# =============================================================================

FROM python:3.11-slim AS base

# Prevent Python from writing .pyc files and buffering stdout/stderr
# - PYTHONDONTWRITEBYTECODE: keeps image small, avoids __pycache__ drift
# - PYTHONUNBUFFERED: critical for Docker logs to stream in real time
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# -----------------------------------------------------------------------------
# Layer 1: Install OS dependencies needed to build SciPy wheels
# (gcc, gfortran, libopenblas64-dev only needed at build time)
# -----------------------------------------------------------------------------
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        gcc \
        gfortran \
        libopenblas-dev \
        curl \
 && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Layer 2: Install Python dependencies (cached unless requirements.txt changes)
# -----------------------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Layer 3: Copy application code
# -----------------------------------------------------------------------------
COPY app/ ./app/
COPY tests/ ./tests/

# -----------------------------------------------------------------------------
# Create and switch to a non-root user for security (Rubric: production-grade)
# -----------------------------------------------------------------------------
RUN groupadd --system appgroup \
 && useradd --system --gid appgroup --create-home --shell /bin/bash appuser \
 && chown -R appuser:appgroup /app
USER appuser

# -----------------------------------------------------------------------------
# Expose the FastAPI port
# -----------------------------------------------------------------------------
EXPOSE 8000

# -----------------------------------------------------------------------------
# Container-level healthcheck (Render also pings /health separately)
# -----------------------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# -----------------------------------------------------------------------------
# Entrypoint — single uvicorn process, binds 0.0.0.0:8000 for external traffic
# -----------------------------------------------------------------------------
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
