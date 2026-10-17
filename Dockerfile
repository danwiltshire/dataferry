FROM python:3.14-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.8.21 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY uv.lock pyproject.toml ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev

COPY dataferry/ dataferry/
COPY alembic/ alembic/
COPY alembic.ini .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.14-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH"

# postgresql-client-18 (matching the postgres:18 server used in docker-compose)
# provides pg_dump/pg_restore for the agent; tini reaps zombie subprocesses and
# forwards signals correctly to the Python process.
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg lsb-release tini && \
    install -d /usr/share/postgresql-common/pgdg && \
    curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc --fail https://www.postgresql.org/media/keys/ACCC4CF8.asc && \
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends postgresql-client-18 && \
    apt-get purge -y curl gnupg lsb-release && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -m -d /app -s /bin/false appuser

WORKDIR /app

COPY --from=build --chown=appuser:appgroup /app .

USER appuser

ENTRYPOINT ["/usr/bin/tini", "--"]

# Server
# CMD ["python", "-m", "uvicorn", "dataferry.server:app", "--host", "0.0.0.0", "--port", "8000"]

# Agent
# CMD ["python", "-m", "dataferry.agent"]
