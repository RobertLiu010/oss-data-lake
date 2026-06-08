# ---------- Stage 1: Build ----------
FROM python:3.11-slim AS builder

WORKDIR /app

# Build args for optional dependencies
ARG EXTRAS=""

COPY pyproject.toml ./
COPY app/ ./app/
RUN pip install --no-cache-dir --upgrade pip setuptools \
    && pip wheel --no-cache-dir --wheel-dir /wheels ".${EXTRAS}"

# ---------- Stage 2: Runtime ----------
FROM python:3.11-slim

# Build arg: storage backend tag for image labeling
ARG STORAGE_BACKEND=local

LABEL maintainer="vector-lake"
LABEL org.opencontainers.image.title="vector-lake"
LABEL org.opencontainers.image.description="OSS-based knowledge lake with Entity → Rep → Chunk → Index model"
LABEL org.opencontainers.image.version="0.1.0"
LABEL vector-lake.storage-backend="${STORAGE_BACKEND}"

# Create non-root user
RUN groupadd -r vectorlake && useradd -r -g vectorlake -d /app vectorlake

WORKDIR /app

# Install runtime deps from wheels
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --find-links /wheels vector-lake \
    && rm -rf /wheels

# Copy app code and config
COPY --chown=vectorlake:vectorlake app/ ./app/
COPY --chown=vectorlake:vectorlake config.yaml ./

# Create data directories (local backend)
RUN mkdir -p /app/data /app/lance_data && chown -R vectorlake:vectorlake /app/data /app/lance_data

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

USER vectorlake

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
