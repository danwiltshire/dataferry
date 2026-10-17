import os
import shutil

# Must be set before any `dataferry.*` module is imported, since dataferry.db
# creates its engine (and dataferry.agent reads required env vars) at import
# time. Point at a dedicated test database on the same Postgres instance used
# for local dev (docker-compose's `db` service).
os.environ.setdefault("DATABASE_HOST", "localhost")
os.environ.setdefault("DATABASE_PORT", "5432")
os.environ.setdefault("DATABASE_USER", "postgres")
os.environ.setdefault("DATABASE_PASSWORD", "example")
os.environ.setdefault("DATABASE_NAME", "dataferry_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ARTIFACT_DIR", "/tmp/dataferry-test-artifacts")
os.environ.setdefault("JOB_LONG_POLL_TIMEOUT_SECONDS", "1")
# Unused by these fixtures, but dataferry.agent requires them at import time.
os.environ.setdefault("ORCHESTRATOR_URL", "http://test")
os.environ.setdefault("AGENT_CLIENT_ID", "unused")
os.environ.setdefault("AGENT_CLIENT_SECRET", "unused")

import psycopg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from dataferry.config import get_settings
from dataferry.db import engine
from dataferry.models import Base
from dataferry.server import app


def _ensure_test_database_exists() -> None:
    settings = get_settings()
    admin_dsn = (
        f"host={settings.database_host} port={settings.database_port} "
        f"user={settings.database_user} password={settings.database_password} "
        "dbname=postgres"
    )
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (settings.database_name,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{settings.database_name}"')


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _schema():
    _ensure_test_database_exists()
    shutil.rmtree(get_settings().artifact_dir, ignore_errors=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def asgi_transport():
    return ASGITransport(app=app)


async def create_agent(client: AsyncClient, name: str = "test-agent") -> dict:
    response = await client.post("/admin/agents", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


async def create_connection(
    client: AsyncClient,
    agent_id: int,
    *,
    name: str = "conn",
    host: str = "db",
    database_name: str = "app",
    **overrides,
) -> dict:
    body = {
        "name": name,
        "engine": "postgres",
        "host": host,
        "port": 5432,
        "database_name": database_name,
        "credential_source": "static",
        "username": "postgres",
        "password": "example",
        **overrides,
    }
    response = await client.post(f"/admin/agents/{agent_id}/databases", json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def create_job(client: AsyncClient, source_id: int, destination_id: int) -> dict:
    response = await client.post(
        "/admin/jobs",
        json={"source_connection_id": source_id, "destination_connection_id": destination_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def get_token(client: AsyncClient, client_id: str, client_secret: str) -> str:
    response = await client.post(
        "/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]
