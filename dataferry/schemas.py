from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from dataferry.models import CredentialSource, DatabaseEngine, JobPhase, JobStatus


class AgentCreate(BaseModel):
    name: str


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    client_id: str
    created_at: datetime


class AgentCreated(AgentOut):
    # Only ever returned once, at creation time.
    client_secret: str


class DatabaseConnectionCreate(BaseModel):
    name: str
    engine: DatabaseEngine
    host: str
    port: int
    database_name: str

    credential_source: CredentialSource
    username: str | None = None
    password: str | None = None
    aws_secret_arn: str | None = None

    @model_validator(mode="after")
    def _check_credentials(self) -> "DatabaseConnectionCreate":
        if self.credential_source == CredentialSource.STATIC:
            if not self.username or not self.password:
                raise ValueError(
                    "username and password are required for the static credential source"
                )
        elif self.credential_source == CredentialSource.AWS_SECRETS_MANAGER:
            if not self.aws_secret_arn:
                raise ValueError(
                    "aws_secret_arn is required for the aws_secrets_manager credential source"
                )
        return self


class DatabaseConnectionClone(BaseModel):
    """Creates a new connection re-using an existing one's host/credentials,
    for a new database on the same host (the password is never exposed to
    the client for this, since the server copies it internally)."""

    database_name: str
    name: str | None = None


class DatabaseConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int
    name: str
    engine: DatabaseEngine
    host: str
    port: int
    database_name: str
    credential_source: CredentialSource
    # Password is intentionally never returned.
    username: str | None
    aws_secret_arn: str | None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class JobCreate(BaseModel):
    source_connection_id: int
    destination_connection_id: int


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_connection_id: int
    destination_connection_id: int
    phase: JobPhase
    status: JobStatus
    leased_by_agent_id: int | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class ResolvedDatabaseConnection(BaseModel):
    """Database connection details with credentials resolved, sent only to the
    one agent authorized (via its agent_id FK) to act on this connection."""

    engine: DatabaseEngine
    host: str
    port: int
    database_name: str
    username: str
    password: str


class JobAssignment(BaseModel):
    job_id: int
    phase: JobPhase
    connection: ResolvedDatabaseConnection
    lease_seconds: int


class JobStatusUpdate(BaseModel):
    status: JobStatus
    error: str | None = None


class JobLogAppend(BaseModel):
    text: str
