import enum
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DatabaseEngine(enum.StrEnum):
    POSTGRES = "postgres"
    MYSQL = "mysql"


class CredentialSource(enum.StrEnum):
    # Username/password stored directly on the DatabaseConnection row.
    STATIC = "static"
    # Fetched at connection time from an AWS Secrets Manager secret (RDS-managed
    # secrets for a cluster or instance share the same JSON schema).
    AWS_SECRETS_MANAGER = "aws_secrets_manager"


class JobPhase(enum.StrEnum):
    DUMP = "dump"
    RESTORE = "restore"


class JobStatus(enum.StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    KILLED = "killed"


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    client_id: Mapped[str] = mapped_column(
        unique=True, index=True, default=lambda: str(uuid.uuid4())
    )
    client_secret_hash: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    databases: Mapped[list["DatabaseConnection"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )


class DatabaseConnection(Base):
    __tablename__ = "database_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    name: Mapped[str]
    engine: Mapped[DatabaseEngine]
    host: Mapped[str]
    port: Mapped[int]
    database_name: Mapped[str]

    credential_source: Mapped[CredentialSource]

    # Populated when credential_source == STATIC.
    username: Mapped[str | None] = mapped_column(default=None)
    password: Mapped[str | None] = mapped_column(default=None)

    # Populated when credential_source == AWS_SECRETS_MANAGER. The secret is
    # expected to contain username/password (and optionally host/port/dbname)
    # in the same JSON schema AWS uses for RDS-managed secrets.
    aws_secret_arn: Mapped[str | None] = mapped_column(default=None)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    agent: Mapped["Agent"] = relationship(back_populates="databases")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_connection_id: Mapped[int] = mapped_column(
        ForeignKey("database_connections.id")
    )
    destination_connection_id: Mapped[int] = mapped_column(
        ForeignKey("database_connections.id")
    )

    # DUMP runs on the source agent, then flips to RESTORE on the destination agent.
    phase: Mapped[JobPhase] = mapped_column(default=JobPhase.DUMP)
    status: Mapped[JobStatus] = mapped_column(default=JobStatus.PENDING)

    leased_by_agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id"), default=None
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(default=None)

    error: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    source_connection: Mapped["DatabaseConnection"] = relationship(
        foreign_keys=[source_connection_id]
    )
    destination_connection: Mapped["DatabaseConnection"] = relationship(
        foreign_keys=[destination_connection_id]
    )
