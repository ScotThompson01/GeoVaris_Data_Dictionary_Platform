import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ObjectType = Literal[
    "file",
    "worksheet",
    "table",
    "view",
]


class SourceObjectCreate(BaseModel):
    data_source_id: uuid.UUID
    object_type: ObjectType
    object_name: str = Field(min_length=1, max_length=255)
    schema_name: str | None = None
    native_name: str | None = None
    description: str | None = None
    row_count: int | None = Field(default=None, ge=0)


class SourceObjectRead(BaseModel):
    id: uuid.UUID
    data_source_id: uuid.UUID
    object_type: str
    object_name: str
    schema_name: str | None
    native_name: str | None
    description: str | None
    row_count: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)