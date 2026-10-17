import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from dataferry.auth import get_current_agent
from dataferry.config import get_settings
from dataferry.credentials import get_credential_provider
from dataferry.db import get_db
from dataferry.models import Agent, DatabaseConnection, Job, JobPhase, JobStatus
from dataferry.schemas import (
    JobAssignment,
    JobLogAppend,
    JobStatusUpdate,
    ResolvedDatabaseConnection,
)
from dataferry.storage import artifact_path, delete_artifact, log_path

router = APIRouter(prefix="/agent", tags=["agent"])


async def _reap_expired_leases(db: AsyncSession) -> None:
    await db.execute(
        update(Job)
        .where(Job.status == JobStatus.LEASED, Job.lease_expires_at < datetime.now(UTC))
        .values(status=JobStatus.PENDING, leased_by_agent_id=None, lease_expires_at=None)
    )
    await db.commit()


async def _claim_next_job(db: AsyncSession, agent: Agent) -> Job | None:
    source_conn = aliased(DatabaseConnection)
    dest_conn = aliased(DatabaseConnection)

    stmt = (
        select(Job)
        .join(source_conn, Job.source_connection_id == source_conn.id)
        .join(dest_conn, Job.destination_connection_id == dest_conn.id)
        .where(
            Job.status == JobStatus.PENDING,
            or_(
                and_(Job.phase == JobPhase.DUMP, source_conn.agent_id == agent.id),
                and_(Job.phase == JobPhase.RESTORE, dest_conn.agent_id == agent.id),
            ),
        )
        .order_by(Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = (await db.execute(stmt)).scalar_one_or_none()
    if job is None:
        return None

    settings = get_settings()
    job.status = JobStatus.LEASED
    job.leased_by_agent_id = agent.id
    job.lease_expires_at = datetime.now(UTC) + timedelta(seconds=settings.job_lease_seconds)
    await db.commit()
    await db.refresh(job)
    return job


async def _acting_connection(db: AsyncSession, job: Job) -> DatabaseConnection:
    connection_id = (
        job.source_connection_id if job.phase == JobPhase.DUMP else job.destination_connection_id
    )
    connection = await db.get(DatabaseConnection, connection_id)
    assert connection is not None
    return connection


@router.get("/jobs/next", response_model=JobAssignment | None)
async def get_next_job(
    agent: Agent = Depends(get_current_agent), db: AsyncSession = Depends(get_db)
):
    settings = get_settings()
    deadline = asyncio.get_running_loop().time() + settings.job_long_poll_timeout_seconds
    while True:
        await _reap_expired_leases(db)
        job = await _claim_next_job(db, agent)
        if job is not None:
            break
        if asyncio.get_running_loop().time() >= deadline:
            return Response(status_code=204)
        await asyncio.sleep(1)

    connection = await _acting_connection(db, job)
    credentials = await get_credential_provider(connection).get_credentials()
    return JobAssignment(
        job_id=job.id,
        phase=job.phase,
        lease_seconds=settings.job_lease_seconds,
        connection=ResolvedDatabaseConnection(
            engine=connection.engine,
            host=connection.host,
            port=connection.port,
            database_name=connection.database_name,
            username=credentials.username,
            password=credentials.password,
        ),
    )


async def _get_leased_job_or_404(job_id: int, agent: Agent, db: AsyncSession) -> Job:
    job = await db.get(Job, job_id)
    if job is None or job.leased_by_agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/heartbeat", status_code=204)
async def heartbeat(
    job_id: int,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_leased_job_or_404(job_id, agent, db)
    settings = get_settings()
    job.lease_expires_at = datetime.now(UTC) + timedelta(seconds=settings.job_lease_seconds)
    await db.commit()


@router.post("/jobs/{job_id}/status", status_code=204)
async def report_status(
    job_id: int,
    body: JobStatusUpdate,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_leased_job_or_404(job_id, agent, db)

    if body.status == JobStatus.RUNNING:
        job.status = JobStatus.RUNNING
    elif body.status == JobStatus.SUCCEEDED and job.phase == JobPhase.DUMP:
        # Dump finished: hand the job off to the destination agent.
        job.phase = JobPhase.RESTORE
        job.status = JobStatus.PENDING
        job.leased_by_agent_id = None
        job.lease_expires_at = None
    elif body.status == JobStatus.SUCCEEDED:
        job.status = JobStatus.SUCCEEDED
        delete_artifact(job.id)
    elif body.status == JobStatus.FAILED:
        job.status = JobStatus.FAILED
        job.error = body.error
        delete_artifact(job.id)
    elif body.status == JobStatus.KILLED:
        # Not a real failure: make it eligible for another agent immediately.
        job.status = JobStatus.PENDING
        job.leased_by_agent_id = None
        job.lease_expires_at = None
        if job.phase == JobPhase.DUMP:
            delete_artifact(job.id)
    else:
        raise HTTPException(status_code=400, detail="Unsupported status transition")

    await db.commit()


@router.post("/jobs/{job_id}/log", status_code=204)
async def append_log(
    job_id: int,
    body: JobLogAppend,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    await _get_leased_job_or_404(job_id, agent, db)
    with log_path(job_id).open("a") as f:
        f.write(body.text)


@router.put("/jobs/{job_id}/artifact", status_code=204)
async def upload_artifact(
    job_id: int,
    request: Request,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_leased_job_or_404(job_id, agent, db)
    if job.phase != JobPhase.DUMP:
        raise HTTPException(status_code=409, detail="Job is not in the dump phase")

    with artifact_path(job.id).open("wb") as f:
        async for chunk in request.stream():
            f.write(chunk)


@router.get("/jobs/{job_id}/artifact")
async def download_artifact(
    job_id: int,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_leased_job_or_404(job_id, agent, db)
    if job.phase != JobPhase.RESTORE:
        raise HTTPException(status_code=409, detail="Job is not in the restore phase")

    path = artifact_path(job.id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")

    def _iter_file():
        with path.open("rb") as f:
            while chunk := f.read(1024 * 1024):
                yield chunk

    return StreamingResponse(_iter_file(), media_type="application/octet-stream")
