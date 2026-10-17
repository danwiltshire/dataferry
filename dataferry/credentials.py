import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache

import boto3

from dataferry.models import CredentialSource, DatabaseConnection


@dataclass(frozen=True)
class DatabaseCredentials:
    username: str
    password: str


class CredentialProvider(ABC):
    @abstractmethod
    async def get_credentials(self) -> DatabaseCredentials: ...


class StaticCredentialProvider(CredentialProvider):
    """Credentials hard-coded on the DatabaseConnection row."""

    def __init__(self, db_connection: DatabaseConnection) -> None:
        if db_connection.username is None or db_connection.password is None:
            raise ValueError(
                f"DatabaseConnection {db_connection.id} is missing static credentials"
            )
        self._username = db_connection.username
        self._password = db_connection.password

    async def get_credentials(self) -> DatabaseCredentials:
        return DatabaseCredentials(username=self._username, password=self._password)


class AwsSecretsManagerCredentialProvider(CredentialProvider):
    """Credentials fetched from an AWS Secrets Manager secret (RDS-managed
    secrets for a cluster or instance both use the same JSON schema)."""

    def __init__(self, db_connection: DatabaseConnection) -> None:
        if db_connection.aws_secret_arn is None:
            raise ValueError(
                f"DatabaseConnection {db_connection.id} is missing aws_secret_arn"
            )
        self._secret_arn = db_connection.aws_secret_arn

    @property
    def _region(self) -> str:
        # ARN format: arn:aws:secretsmanager:<region>:<account-id>:secret:<name>
        return self._secret_arn.split(":")[3]

    async def get_credentials(self) -> DatabaseCredentials:
        secret = await asyncio.to_thread(self._fetch_secret)
        return DatabaseCredentials(
            username=secret["username"], password=secret["password"]
        )

    def _fetch_secret(self) -> dict:
        client = _secrets_manager_client(self._region)
        response = client.get_secret_value(SecretId=self._secret_arn)
        return json.loads(response["SecretString"])


@lru_cache
def _secrets_manager_client(region: str):
    return boto3.client("secretsmanager", region_name=region)


def get_credential_provider(db_connection: DatabaseConnection) -> CredentialProvider:
    match db_connection.credential_source:
        case CredentialSource.STATIC:
            return StaticCredentialProvider(db_connection)
        case CredentialSource.AWS_SECRETS_MANAGER:
            return AwsSecretsManagerCredentialProvider(db_connection)
    raise ValueError(f"Unsupported credential source: {db_connection.credential_source}")
