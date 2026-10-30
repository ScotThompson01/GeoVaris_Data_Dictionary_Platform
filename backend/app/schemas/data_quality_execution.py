"""Request and response schemas for Phase 5D Data Quality execution."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class RangeRuleExecutionRequest(BaseModel):
    """Runtime PostgreSQL connection details; credentials are not persisted."""

    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(min_length=1, max_length=255)
    username: str = Field(min_length=1, max_length=255)
    password: SecretStr | None = None
    ssl_mode: str | None = Field(default=None, max_length=50)
    connect_timeout_seconds: int = Field(default=10, ge=1, le=120)


class RangeRuleExecutionResponse(BaseModel):
    """Aggregate execution results without source records or credentials."""

    model_config = ConfigDict(extra="forbid")

    execution_id: uuid.UUID
    project_id: uuid.UUID
    rule_id: uuid.UUID
    version_id: uuid.UUID
    status: Literal["succeeded"]
    total_count: int = Field(ge=0)
    passing_count: int = Field(ge=0)
    violation_count: int = Field(ge=0)
    started_at: datetime
    completed_at: datetime
