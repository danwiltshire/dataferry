import pytest
from httpx import AsyncClient

from tests.conftest import create_agent, create_connection, create_job, get_token


async def test_create_agent_returns_client_credentials(client: AsyncClient):
    agent = await create_agent(client, name="agent-a")

    assert agent["name"] == "agent-a"
    assert agent["client_id"]
    assert agent["client_secret"]


async def test_list_and_get_agent(client: AsyncClient):
    created = await create_agent(client, name="agent-b")

    listed = await client.get("/admin/agents")
    assert listed.status_code == 200
    assert any(a["id"] == created["id"] for a in listed.json())

    fetched = await client.get(f"/admin/agents/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["client_id"] == created["client_id"]
    # The secret is only ever returned once, at creation time.
    assert "client_secret" not in fetched.json()


async def test_get_unknown_agent_404s(client: AsyncClient):
    response = await client.get("/admin/agents/999999")
    assert response.status_code == 404


async def test_oauth_token_issued_for_valid_credentials(client: AsyncClient):
    agent = await create_agent(client)

    token = await get_token(client, agent["client_id"], agent["client_secret"])

    assert token


async def test_oauth_token_rejected_for_wrong_secret(client: AsyncClient):
    agent = await create_agent(client)

    response = await client.post(
        "/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": agent["client_id"],
            "client_secret": "wrong-secret",
        },
    )

    assert response.status_code == 401


async def test_oauth_token_rejected_after_agent_revoked(client: AsyncClient):
    agent = await create_agent(client)
    await client.delete(f"/admin/agents/{agent['id']}")

    response = await client.post(
        "/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": agent["client_id"],
            "client_secret": agent["client_secret"],
        },
    )

    assert response.status_code == 401


async def test_oauth_token_rejects_unsupported_grant_type(client: AsyncClient):
    agent = await create_agent(client)

    response = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": agent["client_id"],
            "client_secret": agent["client_secret"],
        },
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    "overrides",
    [
        {"credential_source": "static", "username": None, "password": None},
        {"credential_source": "aws_secrets_manager", "aws_secret_arn": None},
    ],
)
async def test_create_database_connection_requires_matching_credentials(
    client: AsyncClient, overrides: dict
):
    agent = await create_agent(client)

    response = await client.post(
        f"/admin/agents/{agent['id']}/databases",
        json={
            "name": "conn",
            "engine": "postgres",
            "host": "db",
            "port": 5432,
            "database_name": "app",
            **overrides,
        },
    )

    assert response.status_code == 422


async def test_create_database_connection_never_returns_password(client: AsyncClient):
    agent = await create_agent(client)

    connection = await create_connection(client, agent["id"])

    assert "password" not in connection
    assert connection["username"] == "postgres"


async def test_database_connection_scoped_to_agent(client: AsyncClient):
    agent_a = await create_agent(client, name="agent-a")
    agent_b = await create_agent(client, name="agent-b")
    connection = await create_connection(client, agent_a["id"])

    # A connection created under agent A is not visible/deletable under agent B.
    listed = await client.get(f"/admin/agents/{agent_b['id']}/databases")
    assert listed.json() == []

    delete_response = await client.delete(
        f"/admin/agents/{agent_b['id']}/databases/{connection['id']}"
    )
    assert delete_response.status_code == 404


async def test_clone_database_connection_copies_credentials_without_exposing_password(
    client: AsyncClient,
):
    agent = await create_agent(client)
    template = await create_connection(client, agent["id"], name="source", database_name="mydb")

    response = await client.post(
        f"/admin/agents/{agent['id']}/databases/{template['id']}/clone",
        json={"database_name": "mydb_snapshot"},
    )

    assert response.status_code == 201
    clone = response.json()
    assert clone["database_name"] == "mydb_snapshot"
    assert clone["host"] == template["host"]
    assert clone["credential_source"] == template["credential_source"]
    assert clone["username"] == template["username"]
    assert "password" not in clone


async def test_clone_database_connection_requires_matching_agent(client: AsyncClient):
    owner = await create_agent(client, name="owner")
    other = await create_agent(client, name="other")
    template = await create_connection(client, owner["id"])

    response = await client.post(
        f"/admin/agents/{other['id']}/databases/{template['id']}/clone",
        json={"database_name": "mydb_snapshot"},
    )

    assert response.status_code == 404


async def test_create_job_requires_existing_connections(client: AsyncClient):
    response = await client.post(
        "/admin/jobs",
        json={"source_connection_id": 999999, "destination_connection_id": 999998},
    )
    assert response.status_code == 404


async def test_agent_endpoints_require_bearer_token(client: AsyncClient):
    response = await client.get("/agent/jobs/next", params={"timeout": 0})
    assert response.status_code in (401, 403)


async def test_agent_endpoints_reject_invalid_token(client: AsyncClient):
    response = await client.get(
        "/agent/jobs/next",
        params={"timeout": 0},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


async def test_agent_sees_no_job_when_none_pending(client: AsyncClient):
    agent = await create_agent(client)
    token = await get_token(client, agent["client_id"], agent["client_secret"])

    response = await client.get(
        "/agent/jobs/next", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 204


async def test_agent_only_sees_jobs_for_its_own_connections(client: AsyncClient):
    owner = await create_agent(client, name="owner")
    other = await create_agent(client, name="bystander")
    source = await create_connection(client, owner["id"], name="src")
    destination = await create_connection(client, owner["id"], name="dst")
    await create_job(client, source["id"], destination["id"])

    other_token = await get_token(client, other["client_id"], other["client_secret"])
    response = await client.get(
        "/agent/jobs/next", headers={"Authorization": f"Bearer {other_token}"}
    )

    assert response.status_code == 204


async def test_full_job_lifecycle_dump_then_restore(client: AsyncClient):
    agent = await create_agent(client)
    source = await create_connection(client, agent["id"], name="src", database_name="app_src")
    destination = await create_connection(
        client, agent["id"], name="dst", database_name="app_dst"
    )
    job = await create_job(client, source["id"], destination["id"])
    token = await get_token(client, agent["client_id"], agent["client_secret"])
    headers = {"Authorization": f"Bearer {token}"}

    # Dump phase: agent leases the job and gets the source connection's creds.
    assignment = await client.get("/agent/jobs/next", headers=headers)
    assert assignment.status_code == 200
    body = assignment.json()
    assert body["job_id"] == job["id"]
    assert body["phase"] == "dump"
    assert body["connection"]["database_name"] == "app_src"
    assert body["connection"]["password"] == "example"

    heartbeat = await client.post(f"/agent/jobs/{job['id']}/heartbeat", headers=headers)
    assert heartbeat.status_code == 204

    running = await client.post(
        f"/agent/jobs/{job['id']}/status", json={"status": "running"}, headers=headers
    )
    assert running.status_code == 204

    upload = await client.put(
        f"/agent/jobs/{job['id']}/artifact", content=b"fake dump bytes", headers=headers
    )
    assert upload.status_code == 204

    dumped = await client.post(
        f"/agent/jobs/{job['id']}/status", json={"status": "succeeded"}, headers=headers
    )
    assert dumped.status_code == 204

    job_after_dump = await client.get(f"/admin/jobs/{job['id']}")
    assert job_after_dump.json()["phase"] == "restore"
    assert job_after_dump.json()["status"] == "pending"
    assert job_after_dump.json()["leased_by_agent_id"] is None

    # Restore phase: agent leases it again and gets the destination's creds.
    assignment2 = await client.get("/agent/jobs/next", headers=headers)
    assert assignment2.status_code == 200
    body2 = assignment2.json()
    assert body2["phase"] == "restore"
    assert body2["connection"]["database_name"] == "app_dst"

    download = await client.get(f"/agent/jobs/{job['id']}/artifact", headers=headers)
    assert download.status_code == 200
    assert download.content == b"fake dump bytes"

    finished = await client.post(
        f"/agent/jobs/{job['id']}/status", json={"status": "succeeded"}, headers=headers
    )
    assert finished.status_code == 204

    job_final = await client.get(f"/admin/jobs/{job['id']}")
    assert job_final.json()["status"] == "succeeded"

    # The artifact is cleaned up once the job fully succeeds.
    missing_artifact = await client.get(f"/agent/jobs/{job['id']}/artifact", headers=headers)
    assert missing_artifact.status_code == 404


async def test_job_log_append_and_download(client: AsyncClient):
    agent = await create_agent(client)
    source = await create_connection(client, agent["id"], name="src", database_name="app_src")
    destination = await create_connection(
        client, agent["id"], name="dst", database_name="app_dst"
    )
    job = await create_job(client, source["id"], destination["id"])
    token = await get_token(client, agent["client_id"], agent["client_secret"])
    headers = {"Authorization": f"Bearer {token}"}

    # No log yet.
    missing = await client.get(f"/admin/jobs/{job['id']}/log")
    assert missing.status_code == 404

    await client.get("/agent/jobs/next", headers=headers)

    append1 = await client.post(
        f"/agent/jobs/{job['id']}/log", json={"text": "line one\n"}, headers=headers
    )
    assert append1.status_code == 204
    append2 = await client.post(
        f"/agent/jobs/{job['id']}/log", json={"text": "line two\n"}, headers=headers
    )
    assert append2.status_code == 204

    download = await client.get(f"/admin/jobs/{job['id']}/log")
    assert download.status_code == 200
    assert download.content == b"line one\nline two\n"
    assert (
        download.headers["content-disposition"]
        == f'attachment; filename="job-{job["id"]}.log"'
    )


async def test_job_log_stream_returns_sse_content_type(client: AsyncClient):
    agent = await create_agent(client)
    source = await create_connection(client, agent["id"], name="src", database_name="app_src")
    destination = await create_connection(
        client, agent["id"], name="dst", database_name="app_dst"
    )
    job = await create_job(client, source["id"], destination["id"])
    token = await get_token(client, agent["client_id"], agent["client_secret"])
    headers = {"Authorization": f"Bearer {token}"}

    await client.get("/agent/jobs/next", headers=headers)
    await client.post(
        f"/agent/jobs/{job['id']}/log", json={"text": "streamed line\n"}, headers=headers
    )
    # Kill the job first so the tail loop's poll sees a terminal status and
    # exits immediately instead of polling forever.
    await client.post(
        f"/agent/jobs/{job['id']}/status", json={"status": "killed"}, headers=headers
    )

    async with client.stream("GET", f"/admin/jobs/{job['id']}/log/stream") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = b""
        async for chunk in response.aiter_bytes():
            body += chunk
        assert b"data: streamed line" in body
        assert b"event: end" in body


async def test_job_failure_records_error_and_clears_artifact(client: AsyncClient):
    agent = await create_agent(client)
    source = await create_connection(client, agent["id"], name="src")
    destination = await create_connection(client, agent["id"], name="dst")
    job = await create_job(client, source["id"], destination["id"])
    token = await get_token(client, agent["client_id"], agent["client_secret"])
    headers = {"Authorization": f"Bearer {token}"}

    await client.get("/agent/jobs/next", headers=headers)
    await client.put(f"/agent/jobs/{job['id']}/artifact", content=b"x", headers=headers)

    failed = await client.post(
        f"/agent/jobs/{job['id']}/status",
        json={"status": "failed", "error": "pg_dump exited 1"},
        headers=headers,
    )
    assert failed.status_code == 204

    job_after = await client.get(f"/admin/jobs/{job['id']}")
    assert job_after.json()["status"] == "failed"
    assert job_after.json()["error"] == "pg_dump exited 1"

    # Job never left the dump phase, so the phase check rejects this before
    # the (already-deleted) artifact would even be looked up.
    missing_artifact = await client.get(f"/agent/jobs/{job['id']}/artifact", headers=headers)
    assert missing_artifact.status_code == 409


async def test_killed_dump_job_is_rescheduled(client: AsyncClient):
    agent = await create_agent(client)
    source = await create_connection(client, agent["id"], name="src")
    destination = await create_connection(client, agent["id"], name="dst")
    job = await create_job(client, source["id"], destination["id"])
    token = await get_token(client, agent["client_id"], agent["client_secret"])
    headers = {"Authorization": f"Bearer {token}"}

    await client.get("/agent/jobs/next", headers=headers)
    killed = await client.post(
        f"/agent/jobs/{job['id']}/status", json={"status": "killed"}, headers=headers
    )
    assert killed.status_code == 204

    job_after = await client.get(f"/admin/jobs/{job['id']}")
    assert job_after.json()["status"] == "pending"
    assert job_after.json()["phase"] == "dump"
    assert job_after.json()["leased_by_agent_id"] is None


async def test_cannot_act_on_a_job_not_leased_to_you(client: AsyncClient):
    owner = await create_agent(client, name="owner")
    other = await create_agent(client, name="other")
    source = await create_connection(client, owner["id"], name="src")
    destination = await create_connection(client, owner["id"], name="dst")
    job = await create_job(client, source["id"], destination["id"])

    other_token = await get_token(client, other["client_id"], other["client_secret"])
    response = await client.post(
        f"/agent/jobs/{job['id']}/heartbeat",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404
