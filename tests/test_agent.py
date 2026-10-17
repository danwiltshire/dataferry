import asyncio
from pathlib import Path

import pytest
from authlib.integrations.httpx_client import AsyncOAuth2Client
from httpx import ASGITransport, AsyncClient

import dataferry.agent as agent_module
from tests.conftest import create_agent, create_connection, create_job


async def _oauth_client(transport: ASGITransport, client_id: str, client_secret: str):
    # fetch_token() below already opens the underlying connection, so callers
    # must not also enter it as an `async with` context manager; instead close
    # it explicitly with `await client.aclose()` once done.
    client = AsyncOAuth2Client(
        client_id=client_id,
        client_secret=client_secret,
        token_endpoint="http://test/oauth/token",
        token_endpoint_auth_method="client_secret_post",
        grant_type="client_credentials",
        transport=transport,
        base_url="http://test",
    )
    await client.fetch_token(grant_type="client_credentials")
    return client


async def test_poll_report_upload_download_round_trip(
    client: AsyncClient, asgi_transport: ASGITransport
):
    agent = await create_agent(client)
    source = await create_connection(client, agent["id"], name="src", database_name="app_src")
    destination = await create_connection(
        client, agent["id"], name="dst", database_name="app_dst"
    )
    job = await create_job(client, source["id"], destination["id"])

    oauth_client = await _oauth_client(
        asgi_transport, agent["client_id"], agent["client_secret"]
    )
    assignment = await agent_module._poll_for_job(oauth_client)
    assert assignment is not None
    assert assignment["job_id"] == job["id"]
    assert assignment["phase"] == "dump"
    assert assignment["connection"]["database_name"] == "app_src"

    await agent_module._report_status(oauth_client, job["id"], "running")
    await agent_module._upload_artifact(oauth_client, job["id"], b"dumped bytes")
    await agent_module._report_status(oauth_client, job["id"], "succeeded")

    restore_assignment = await agent_module._poll_for_job(oauth_client)
    assert restore_assignment is not None
    assert restore_assignment["phase"] == "restore"
    assert restore_assignment["connection"]["database_name"] == "app_dst"

    dest_path = Path("/tmp/dataferry-test-artifacts/download-test.dump")
    await agent_module._download_artifact(oauth_client, job["id"], dest_path)
    assert dest_path.read_bytes() == b"dumped bytes"
    dest_path.unlink()

    await agent_module._report_status(oauth_client, job["id"], "succeeded")
    await oauth_client.aclose()

    job_after = await client.get(f"/admin/jobs/{job['id']}")
    assert job_after.json()["status"] == "succeeded"


async def test_poll_for_job_returns_none_when_no_job_available(
    client: AsyncClient, asgi_transport: ASGITransport
):
    agent = await create_agent(client)
    oauth_client = await _oauth_client(
        asgi_transport, agent["client_id"], agent["client_secret"]
    )
    assignment = await agent_module._poll_for_job(oauth_client)
    await oauth_client.aclose()

    assert assignment is None


class _FakeStreamReader:
    def __init__(self, data: bytes) -> None:
        self._remaining: bytes | None = data

    async def read(self, _n: int = -1) -> bytes:
        if self._remaining is None:
            return b""
        data, self._remaining = self._remaining, None
        return data

    async def readline(self) -> bytes:
        if not self._remaining:
            return b""
        line, sep, rest = self._remaining.partition(b"\n")
        self._remaining = rest
        return line + sep


class _FakeStreamWriter:
    def write(self, _data: bytes) -> None:
        pass

    def close(self) -> None:
        pass


class _FakeProcess:
    def __init__(self, stdout: bytes | None = None, returncode: int = 0) -> None:
        self.stdout = _FakeStreamReader(stdout) if stdout is not None else None
        self.stderr = _FakeStreamReader(b"")
        self.stdin = _FakeStreamWriter()
        self._returncode = returncode

    async def wait(self) -> int:
        return self._returncode

    def terminate(self) -> None:
        pass

    def kill(self) -> None:
        pass


@pytest.fixture
def fake_subprocess(monkeypatch):
    """Stands in for pg_dump/pg_restore/psql/createdb so job orchestration can
    be exercised functionally (real HTTP + real test DB) without needing
    Postgres client tools or a second real database on the machine running
    the tests."""
    dump_bytes = b"fake pg_dump output"
    restored: dict[str, bytes] = {}

    async def _fake_exec(*args, **kwargs):
        if args[0] == "pg_dump":
            return _FakeProcess(stdout=dump_bytes)
        if args[0] == "createdb":
            return _FakeProcess()
        if args[0] == "pg_restore":
            restored["content"] = kwargs["stdin"].read()
            return _FakeProcess()
        raise AssertionError(f"unexpected command: {args[0]}")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)
    return {"dump_bytes": dump_bytes, "restored": restored}


async def test_job_runner_runs_dump_then_restore(
    client: AsyncClient, asgi_transport: ASGITransport, fake_subprocess: dict
):
    agent = await create_agent(client)
    source = await create_connection(client, agent["id"], name="src")
    destination = await create_connection(client, agent["id"], name="dst")
    job = await create_job(client, source["id"], destination["id"])

    oauth_client = await _oauth_client(
        asgi_transport, agent["client_id"], agent["client_secret"]
    )
    runner = agent_module.JobRunner(oauth_client)

    dump_assignment = await agent_module._poll_for_job(oauth_client)
    await runner.run_job(dump_assignment)

    restore_assignment = await agent_module._poll_for_job(oauth_client)
    assert restore_assignment is not None
    await runner.run_job(restore_assignment)
    await oauth_client.aclose()

    assert fake_subprocess["restored"]["content"] == fake_subprocess["dump_bytes"]

    job_after = await client.get(f"/admin/jobs/{job['id']}")
    assert job_after.json()["status"] == "succeeded"


async def test_job_runner_reports_failure_on_dump_error(
    client: AsyncClient, asgi_transport: ASGITransport, monkeypatch
):
    agent = await create_agent(client)
    source = await create_connection(client, agent["id"], name="src")
    destination = await create_connection(client, agent["id"], name="dst")
    job = await create_job(client, source["id"], destination["id"])

    async def _failing_exec(*args, **kwargs):
        return _FakeProcess(stdout=b"", returncode=1)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _failing_exec)

    oauth_client = await _oauth_client(
        asgi_transport, agent["client_id"], agent["client_secret"]
    )
    runner = agent_module.JobRunner(oauth_client)
    assignment = await agent_module._poll_for_job(oauth_client)
    await runner.run_job(assignment)
    await oauth_client.aclose()

    job_after = await client.get(f"/admin/jobs/{job['id']}")
    assert job_after.json()["status"] == "failed"
    assert "pg_dump exited 1" in job_after.json()["error"]
