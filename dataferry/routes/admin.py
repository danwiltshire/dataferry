import asyncio
import secrets

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dataferry.db import get_db
from dataferry.models import Agent, DatabaseConnection, Job, JobStatus
from dataferry.schemas import (
    AgentCreate,
    AgentCreated,
    AgentOut,
    DatabaseConnectionClone,
    DatabaseConnectionCreate,
    DatabaseConnectionOut,
    JobCreate,
    JobOut,
)
from dataferry.storage import log_path

router = APIRouter(prefix="/admin", tags=["admin"])

ACTIVE_JOB_STATUSES = {JobStatus.PENDING, JobStatus.LEASED, JobStatus.RUNNING}


def _hash_secret(secret: str) -> str:
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()


async def _get_agent_or_404(agent_id: int, db: AsyncSession) -> Agent:
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/agents", response_model=AgentCreated, status_code=201)
async def create_agent(body: AgentCreate, db: AsyncSession = Depends(get_db)):
    client_secret = secrets.token_urlsafe(32)
    agent = Agent(name=body.name, client_secret_hash=_hash_secret(client_secret))
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return AgentCreated(
        id=agent.id,
        name=agent.name,
        client_id=agent.client_id,
        created_at=agent.created_at,
        client_secret=client_secret,
    )


@router.get("/agents", response_model=list[AgentOut])
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent))
    return result.scalars().all()


@router.get("/agents/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    return await _get_agent_or_404(agent_id, db)


@router.delete("/agents/{agent_id}", status_code=204)
async def revoke_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    agent = await _get_agent_or_404(agent_id, db)
    await db.delete(agent)
    await db.commit()


@router.post(
    "/agents/{agent_id}/databases",
    response_model=DatabaseConnectionOut,
    status_code=201,
)
async def create_database_connection(
    agent_id: int, body: DatabaseConnectionCreate, db: AsyncSession = Depends(get_db)
):
    await _get_agent_or_404(agent_id, db)
    connection = DatabaseConnection(agent_id=agent_id, **body.model_dump())
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return connection


@router.get(
    "/agents/{agent_id}/databases", response_model=list[DatabaseConnectionOut]
)
async def list_database_connections(agent_id: int, db: AsyncSession = Depends(get_db)):
    await _get_agent_or_404(agent_id, db)
    result = await db.execute(
        select(DatabaseConnection).where(DatabaseConnection.agent_id == agent_id)
    )
    return result.scalars().all()


@router.post(
    "/agents/{agent_id}/databases/{connection_id}/clone",
    response_model=DatabaseConnectionOut,
    status_code=201,
)
async def clone_database_connection(
    agent_id: int,
    connection_id: int,
    body: DatabaseConnectionClone,
    db: AsyncSession = Depends(get_db),
):
    await _get_agent_or_404(agent_id, db)
    template = await db.get(DatabaseConnection, connection_id)
    if template is None or template.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Database connection not found")

    clone = DatabaseConnection(
        agent_id=agent_id,
        name=body.name or f"{template.name} ({body.database_name})",
        engine=template.engine,
        host=template.host,
        port=template.port,
        database_name=body.database_name,
        credential_source=template.credential_source,
        # Copied server-side since the template's password/ARN are never
        # serialized back out to the client.
        username=template.username,
        password=template.password,
        aws_secret_arn=template.aws_secret_arn,
    )
    db.add(clone)
    await db.commit()
    await db.refresh(clone)
    return clone


@router.delete("/agents/{agent_id}/databases/{database_id}", status_code=204)
async def delete_database_connection(
    agent_id: int, database_id: int, db: AsyncSession = Depends(get_db)
):
    connection = await db.get(DatabaseConnection, database_id)
    if connection is None or connection.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Database connection not found")
    await db.delete(connection)
    await db.commit()


@router.post("/jobs", response_model=JobOut, status_code=201)
async def create_job(body: JobCreate, db: AsyncSession = Depends(get_db)):
    source = await db.get(DatabaseConnection, body.source_connection_id)
    destination = await db.get(DatabaseConnection, body.destination_connection_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source_connection_id not found")
    if destination is None:
        raise HTTPException(
            status_code=404, detail="destination_connection_id not found"
        )

    job = Job(
        source_connection_id=body.source_connection_id,
        destination_connection_id=body.destination_connection_id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/jobs", response_model=list[JobOut])
async def list_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job))
    return result.scalars().all()


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}/log")
async def download_job_log(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    path = log_path(job_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Log not found")

    def _iter_file():
        with path.open("rb") as f:
            while chunk := f.read(1024 * 1024):
                yield chunk

    return StreamingResponse(
        _iter_file(),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="job-{job_id}.log"'},
    )


@router.get("/jobs/{job_id}/log/stream")
async def stream_job_log(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def _tail():
        path = log_path(job_id)
        position = 0
        while True:
            if path.exists():
                with path.open("rb") as f:
                    f.seek(position)
                    chunk = f.read()
                if chunk:
                    position += len(chunk)
                    for line in chunk.decode(errors="replace").splitlines():
                        yield f"data: {line}\n\n".encode()

            db.expire_all()
            current = await db.get(Job, job_id)
            if current is None or current.status not in ACTIVE_JOB_STATUSES:
                yield b"event: end\ndata: \n\n"
                break
            await asyncio.sleep(1)

    return StreamingResponse(_tail(), media_type="text/event-stream")
