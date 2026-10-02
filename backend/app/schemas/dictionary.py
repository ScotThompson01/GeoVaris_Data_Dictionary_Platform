import uuid

from pydantic import BaseModel


class DictionaryFieldRead(BaseModel):
    field_id: uuid.UUID
    field_name: str
    ordinal_position: int

    native_data_type: str | None
    normalized_data_type: str | None
    max_length: int | None
    numeric_precision: int | None
    numeric_scale: int | None
    default_value: str | None
    source_comment: str | None

    is_nullable: bool | None
    is_primary_key: bool
    is_unique: bool

    source_object_id: uuid.UUID
    object_name: str
    object_type: str
    schema_name: str | None
    native_name: str | None
    object_description: str | None
    object_row_count: int | None

    data_source_id: uuid.UUID
    data_source_name: str
    source_type: str

    department: str | None = None
    data_owner: str | None = None
    is_cde: bool = False
