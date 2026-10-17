import asyncio
import logging
import os
import signal
import tempfile
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

import httpx
import tenacity
from authlib.integrations.httpx_client import AsyncOAuth2Client

ORCHESTRATOR_URL = os.environ["ORCHESTRATOR_URL"]
AGENT_CLIENT_ID = os.environ["AGENT_CLIENT_ID"]
AGENT_CLIENT_SECRET = os.environ["AGENT_CLIENT_SECRET"]

LONG_POLL_TIMEOUT_SECONDS = int(os.environ.get("LONG_POLL_TIMEOUT_SECONDS", "25"))
HEARTBEAT_INTERVAL_SECONDS = int(os.environ.get("HEARTBEAT_INTERVAL_SECONDS", "20"))
SHUTDOWN_GRACE_SECONDS = int(os.environ.get("SHUTDOWN_GRACE_SECONDS", "25"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dataferry.agent")

shutdown_event = asyncio.Event()

_retry = tenacity.retry(
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=30),
    stop=tenacity.stop_after_attempt(5),
    retry=tenacity.retry_if_exception_type(httpx.HTTPError),
    reraise=True,
)


def _new_client() -> AsyncOAuth2Client:
    return AsyncOAuth2Client(
        client_id=AGENT_CLIENT_ID,
        client_secret=AGENT_CLIENT_SECRET,
        token_endpoint=f"{ORCHESTRATOR_URL}/oauth/token",
        token_endpoint_auth_method="client_secret_post",
        grant_type="client_credentials",
        base_url=ORCHESTRATOR_URL,
        timeout=LONG_POLL_TIMEOUT_SECONDS + 10,
    )


@_retry
async def _poll_for_job(client: AsyncOAuth2Client) -> dict | None:
    response = await client.get(
        "/agent/jobs/next", params={"timeout": LONG_POLL_TIMEOUT_SECONDS}
    )
    if response.status_code == 204:
        return None
    response.raise_for_status()
    return response.json()


@_retry
async def _report_status(
    client: AsyncOAuth2Client, job_id: int, status: str, error: str | None = None
) -> None:
    response = await client.post(
        f"/agent/jobs/{job_id}/status", json={"status": status, "error": error}
    )
    response.raise_for_status()


@_retry
async def _upload_artifact(client: AsyncOAuth2Client, job_id: int, data: bytes) -> None:
    # Uploaded as plain in-memory bytes (real Content-Length, no chunked
    # encoding) rather than streamed; the server never handled streamed
    # chunked request bodies reliably, and authlib's bearer-token auth flow
    # fully buffers the request body regardless.
    response = await client.put(f"/agent/jobs/{job_id}/artifact", content=data)
    response.raise_for_status()


@_retry
async def _download_artifact(client: AsyncOAuth2Client, job_id: int, dest: Path) -> None:
    # Downloaded to a fresh file each attempt so a failed/partial download is
    # simply retried from scratch rather than left half-written.
    async with client.stream("GET", f"/agent/jobs/{job_id}/artifact") as response:
        response.raise_for_status()
        with dest.open("wb") as f:
            async for chunk in response.aiter_bytes():
                f.write(chunk)


async def _heartbeat_loop(client: AsyncOAuth2Client, job_id: int) -> None:
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            await client.post(f"/agent/jobs/{job_id}/heartbeat")
    except asyncio.CancelledError:
        pass
    except httpx.HTTPError:
        logger.exception("job %s: heartbeat failed", job_id)


class JobLogger:
    """Batches pg_dump/pg_restore output and periodically flushes it to the
    server, so the web UI can tail/download the real subprocess output."""

    def __init__(self, client: AsyncOAuth2Client, job_id: int) -> None:
        self.client = client
        self.job_id = job_id
        self._buffer: list[str] = []
        # Kept for short error summaries even though the full text already
        # went to the server as it was flushed.
        self._recent: deque[str] = deque(maxlen=20)

    def log(self, message: str) -> None:
        timestamp = datetime.now(UTC).strftime("%H:%M:%S")
        self._buffer.append(f"[{timestamp}] {message}")
        self._recent.append(message)

    def recent_text(self) -> str:
        return "\n".join(self._recent)

    async def flush(self) -> None:
        if not self._buffer:
            return
        text = "\n".join(self._buffer) + "\n"
        self._buffer = []
        try:
            response = await self.client.post(f"/agent/jobs/{self.job_id}/log", json={"text": text})
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception("job %s: failed to flush log", self.job_id)

    async def flush_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(1)
                await self.flush()
        except asyncio.CancelledError:
            pass


async def _forward_stderr(stream: asyncio.StreamReader | None, log: JobLogger) -> None:
    if stream is None:
        return
    while line := await stream.readline():
        log.log(line.decode(errors="replace").rstrip("\n"))


class JobRunner:
    """Runs at most one job at a time; tracks its subprocess as instance state
    (rather than a module-level global) so shutdown can terminate it."""

    def __init__(self, client: AsyncOAuth2Client) -> None:
        self.client = client
        self.process: asyncio.subprocess.Process | None = None

    async def _start_process(self, *args: str, **kwargs) -> asyncio.subprocess.Process:
        # Own process group so termination can be sent to the whole group
        # (avoids orphaning e.g. a compression pipe spawned by pg_dump).
        self.process = await asyncio.create_subprocess_exec(
            *args, start_new_session=True, **kwargs
        )
        return self.process

    async def _run_dump(self, job: dict, log: JobLogger) -> None:
        job_id = job["job_id"]
        conn = job["connection"]
        env = {**os.environ, "PGPASSWORD": conn["password"]}
        log.log(
            f"Starting pg_dump of {conn['username']}@{conn['host']}:{conn['port']}/{conn['database_name']}"
        )
        process = await self._start_process(
            "pg_dump",
            "-h", conn["host"],
            "-p", str(conn["port"]),
            "-U", conn["username"],
            "-F", "c",
            "-v",
            conn["database_name"],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        assert process.stdout is not None
        stderr_task = asyncio.create_task(_forward_stderr(process.stderr, log))

        with tempfile.NamedTemporaryFile(prefix=f"job-{job_id}-", suffix=".dump") as tmp:
            tmp_path = Path(tmp.name)
            while chunk := await process.stdout.read(1024 * 1024):
                tmp.write(chunk)
            tmp.flush()

            return_code = await process.wait()
            await stderr_task
            if return_code != 0:
                raise RuntimeError(f"pg_dump exited {return_code}: {log.recent_text()}")

            log.log("pg_dump completed, uploading artifact")
            await _upload_artifact(self.client, job_id, tmp_path.read_bytes())
            log.log("Artifact uploaded")

    async def _ensure_database_exists(self, conn: dict, env: dict, log: JobLogger) -> None:
        log.log(f"Ensuring destination database {conn['database_name']} exists")
        create = await self._start_process(
            "createdb",
            "-h", conn["host"],
            "-p", str(conn["port"]),
            "-U", conn["username"],
            conn["database_name"],
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        return_code = await create.wait()
        stderr = (await create.stderr.read()).decode() if create.stderr else ""
        if stderr.strip():
            log.log(stderr.strip())
        if return_code != 0 and "already exists" not in stderr:
            raise RuntimeError(f"failed creating destination database: {stderr}")

    async def _run_restore(self, job: dict, log: JobLogger) -> None:
        job_id = job["job_id"]
        conn = job["connection"]
        env = {**os.environ, "PGPASSWORD": conn["password"]}

        await self._ensure_database_exists(conn, env, log)

        with tempfile.NamedTemporaryFile(prefix=f"job-{job_id}-", suffix=".dump") as tmp:
            tmp_path = Path(tmp.name)
            log.log("Downloading dump artifact")
            await _download_artifact(self.client, job_id, tmp_path)
            log.log(
                f"Starting pg_restore into {conn['username']}@{conn['host']}:{conn['port']}/{conn['database_name']}"
            )

            with tmp_path.open("rb") as artifact_file:
                process = await self._start_process(
                    "pg_restore",
                    "-h", conn["host"],
                    "-p", str(conn["port"]),
                    "-U", conn["username"],
                    "-d", conn["database_name"],
                    "-v",
                    "--clean",
                    "--if-exists",
                    stdin=artifact_file,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                stderr_task = asyncio.create_task(_forward_stderr(process.stderr, log))
                return_code = await process.wait()
                await stderr_task

            if return_code != 0:
                raise RuntimeError(f"pg_restore exited {return_code}: {log.recent_text()}")
            log.log("pg_restore completed successfully")

    async def run_job(self, job: dict) -> None:
        job_id = job["job_id"]
        heartbeat_task = asyncio.create_task(_heartbeat_loop(self.client, job_id))
        log = JobLogger(self.client, job_id)
        log_flush_task = asyncio.create_task(log.flush_loop())
        try:
            await _report_status(self.client, job_id, "running")
            log.log(f"Job {job_id} phase={job['phase']} started")
            if job["phase"] == "dump":
                await self._run_dump(job, log)
            else:
                await self._run_restore(job, log)
            log.log("Job phase completed successfully")
            await log.flush()
            await _report_status(self.client, job_id, "succeeded")
        except asyncio.CancelledError:
            log.log("Job killed (agent shutting down)")
            await log.flush()
            await _report_status(self.client, job_id, "killed")
            raise
        except Exception as exc:
            logger.exception("job %s failed", job_id)
            log.log(f"Job failed: {exc}")
            await log.flush()
            await _report_status(self.client, job_id, "failed", error=str(exc))
        finally:
            heartbeat_task.cancel()
            log_flush_task.cancel()
            await asyncio.gather(log_flush_task, return_exceptions=True)
            await log.flush()
            self.process = None

    async def terminate(self, job_task: asyncio.Task) -> None:
        try:
            await asyncio.wait_for(asyncio.shield(job_task), timeout=SHUTDOWN_GRACE_SECONDS)
            return
        except TimeoutError:
            pass

        if self.process is not None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except TimeoutError:
                self.process.kill()

        job_task.cancel()
        await asyncio.gather(job_task, return_exceptions=True)


async def main() -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown_event.set)

    async with _new_client() as client:
        await client.fetch_token(grant_type="client_credentials")
        runner = JobRunner(client)
        while not shutdown_event.is_set():
            try:
                job = await _poll_for_job(client)
            except httpx.HTTPError:
                logger.exception("poll failed, backing off")
                await asyncio.sleep(5)
                continue
            if job is None:
                continue

            job_task = asyncio.create_task(runner.run_job(job))
            shutdown_waiter = asyncio.create_task(shutdown_event.wait())
            done, _pending = await asyncio.wait(
                {job_task, shutdown_waiter}, return_when=asyncio.FIRST_COMPLETED
            )
            shutdown_waiter.cancel()
            if job_task not in done:
                await runner.terminate(job_task)


if __name__ == "__main__":
    asyncio.run(main())
