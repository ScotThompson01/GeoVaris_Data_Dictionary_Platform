import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DataFieldCreate(BaseModel):
    source_object_id: uuid.UUID
    field_name: str = Field(min_length=1, max_length=255)
    ordinal_position: int = Field(ge=1)

    native_data_type: str | None = None
    normalized_data_type: str | None = None

    max_length: int | None = Field(default=None, ge=0)
    numeric_precision: int | None = Field(default=None, ge=0)
    numeric_scale: int | None = Field(default=None, ge=0)

    is_nullable: bool | None = None
    is_primary_key: bool = False
    is_unique: bool = False

    default_value: str | None = None
    source_comment: str | None = None


class DataFieldRead(BaseModel):
    id: uuid.UUID
    source_object_id: uuid.UUID
    field_name: str
    ordinal_position: int
    native_data_type: str | None
    normalized_data_type: str | None
    max_length: int | None
    numeric_precision: int | None
    numeric_scale: int | None
    is_nullable: bool | None
    is_primary_key: bool
    is_unique: bool
    default_value: str | None
    source_comment: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)