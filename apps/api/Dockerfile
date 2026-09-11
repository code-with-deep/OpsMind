FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/apps:/app/packages

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY apps ./apps
COPY packages ./packages
COPY data ./data

# P2-16: non-editable install for a production image (editable installs pull in
# extra dev-mode indirection that isn't needed once the source is COPYed in).
RUN pip install --upgrade pip && pip install .

# P2-16: run as a non-root user; the uploads dir must stay writable by it.
RUN groupadd --system opsmind && useradd --system --gid opsmind --home /app opsmind \
    && mkdir -p /app/data/uploads \
    && chown -R opsmind:opsmind /app
USER opsmind

# P2-16: container-level healthcheck against /ready (DB connectivity).
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS "http://127.0.0.1:${API_PORT:-8000}/ready" || exit 1

# Host/port come from environment (.env via Compose) — no hardcoded listen values
CMD ["python", "-m", "api.entrypoint"]
