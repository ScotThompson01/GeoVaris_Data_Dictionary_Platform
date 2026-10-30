import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class PostgreSQLConnectionIdentityCreate(BaseModel):
    """Non-secret PostgreSQL destination registration."""

    model_config = ConfigDict(extra="forbid")

    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535, strict=True)
    database_name: str = Field(min_length=1, max_length=255)

    @field_validator("host", "database_name")
    @classmethod
    def validate_nonblank_value(cls, value: str) -> str:
        value = value.strip()
        if not value or any(character.isspace() for character in value):
            raise ValueError("Value must be nonblank and contain no whitespace.")
        return value


class PostgreSQLConnectionIdentityUpdate(PostgreSQLConnectionIdentityCreate):
    """Destination update with an optional expected-current-state check."""

    expected_current_host: str | None = Field(default=None, max_length=255)
    expected_current_port: int | None = Field(default=None, ge=1, le=65535, strict=True)
    expected_current_database_name: str | None = Field(default=None, max_length=255)

    @field_validator("expected_current_host", "expected_current_database_name")
    @classmethod
    def validate_expected_nonblank_value(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value or any(character.isspace() for character in value):
            raise ValueError("Expected value must be nonblank and contain no whitespace.")
        return value


class PostgreSQLConnectionVerificationRequest(BaseModel):
    """Runtime-only credentials used to verify a registered destination."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=255)
    password: SecretStr | None = None
    connect_timeout_seconds: int = Field(default=10, ge=1, le=30)


class PostgreSQLConnectionIdentityRead(BaseModel):
    """Registered destination and server-controlled verification state."""

    model_config = ConfigDict(from_attributes=True)

    data_source_id: uuid.UUID
    host: str
    port: int
    database_name: str
    is_verified: bool
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime
