import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SourceType = Literal[
    "csv",
    "excel",
    "sql_server",
    "postgresql",
]

ConnectionMode = Literal[
    "file",
    "database",
]


class DataSourceCreate(BaseModel):
    project_id: uuid.UUID

    name: str = Field(
        min_length=1,
        max_length=200,
    )

    source_type: SourceType

    description: str | None = None

    connection_mode: ConnectionMode

    is_active: bool = True


class DataSourceRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    source_type: str
    description: str | None
    connection_mode: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )