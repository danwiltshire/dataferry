from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    database_host: str = "localhost"
    database_port: int = 5432
    database_user: str = "postgres"
    database_password: str = "postgres"
    database_name: str = "dataferry"

    # Signing key for JWT access tokens issued by /oauth/token.
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_seconds: int = 900

    # Local-disk stand-in for an object store (e.g. S3) holding dump artifacts
    # in transit between the source and destination agent.
    artifact_dir: str = "/tmp/dataferry-artifacts"

    job_lease_seconds: int = 60
    job_long_poll_timeout_seconds: int = 25

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
