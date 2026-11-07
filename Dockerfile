# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1

RUN pip install --no-cache-dir uv==0.13.7

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin zasky

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/pyproject.toml /app/uv.lock /app/README.md ./
COPY alembic.ini ./
COPY migrations ./migrations
RUN mkdir -p /app/data && chown -R zasky:zasky /app

USER zasky
# 8099 is the private health endpoint; 8100 is the owner dashboard API.
EXPOSE 8099 8100

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8099/health/live', timeout=3)"

CMD ["python", "-m", "zasky"]
