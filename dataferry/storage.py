from pathlib import Path

from dataferry.config import get_settings


def artifact_path(job_id: int) -> Path:
    """Local-disk stand-in for an object store (e.g. S3) holding dump artifacts
    in transit between the source and destination agent."""
    directory = Path(get_settings().artifact_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{job_id}.dump"


def delete_artifact(job_id: int) -> None:
    artifact_path(job_id).unlink(missing_ok=True)


def log_path(job_id: int) -> Path:
    """pg_dump/pg_restore log for a job, appended to by the agent as it runs
    and kept (unlike the artifact) after the job finishes, for download."""
    directory = Path(get_settings().artifact_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{job_id}.log"
