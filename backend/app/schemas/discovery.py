import uuid

from pydantic import BaseModel, Field, SecretStr


class CSVDiscoveryRequest(BaseModel):
    data_source_id: uuid.UUID

    file_name: str = Field(
        min_length=1,
        max_length=255,
    )


class PostgreSQLDiscoveryRequest(BaseModel):
    """
    Runtime PostgreSQL connection details for metadata discovery.

    The password is accepted as a secret request value and is not
    intended for persistence or inclusion in API responses.
    """

    data_source_id: uuid.UUID

    host: str = Field(
        min_length=1,
        max_length=255,
    )

    port: int = Field(
        default=5432,
        ge=1,
        le=65535,
    )

    database: str = Field(
        min_length=1,
        max_length=255,
    )

    username: str = Field(
        min_length=1,
        max_length=255,
    )

    password: SecretStr | None = None

    ssl_mode: str | None = Field(
        default=None,
        max_length=50,
    )

    connect_timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=120,
    )


class SQLServerDiscoveryRequest(BaseModel):
    """
    Runtime SQL Server connection details for metadata discovery.

    The password is accepted as a secret request value and is not
    intended for persistence or inclusion in API responses.
    """

    data_source_id: uuid.UUID

    host: str = Field(
        min_length=1,
        max_length=255,
    )

    port: int = Field(
        default=1433,
        ge=1,
        le=65535,
    )

    database: str = Field(
        min_length=1,
        max_length=255,
    )

    username: str = Field(
        min_length=1,
        max_length=255,
    )

    password: SecretStr | None = None

    ssl_mode: str | None = Field(
        default=None,
        max_length=50,
    )

    connect_timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=120,
    )