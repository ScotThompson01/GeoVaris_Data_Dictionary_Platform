import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ApprovalStatus = Literal[
    "draft",
    "steward_review",
    "owner_approval",
    "published",
]


class FieldGovernanceMetadataCreate(BaseModel):
    data_field_id: uuid.UUID

    business_name: str | None = Field(
        default=None,
        max_length=255,
    )
    business_definition: str | None = None

    department: str | None = Field(
        default=None,
        max_length=255,
    )
    data_owner: str | None = Field(
        default=None,
        max_length=255,
    )
    data_steward: str | None = Field(
        default=None,
        max_length=255,
    )
    business_process: str | None = Field(
        default=None,
        max_length=255,
    )
    system_of_record: str | None = Field(
        default=None,
        max_length=255,
    )

    is_cde: bool = False

    classification: str | None = Field(
        default=None,
        max_length=100,
    )

    approval_status: ApprovalStatus = "draft"

    notes: str | None = None


class FieldGovernanceMetadataUpdate(BaseModel):
    business_name: str | None = Field(
        default=None,
        max_length=255,
    )
    business_definition: str | None = None

    department: str | None = Field(
        default=None,
        max_length=255,
    )
    data_owner: str | None = Field(
        default=None,
        max_length=255,
    )
    data_steward: str | None = Field(
        default=None,
        max_length=255,
    )
    business_process: str | None = Field(
        default=None,
        max_length=255,
    )
    system_of_record: str | None = Field(
        default=None,
        max_length=255,
    )

    is_cde: bool | None = None

    classification: str | None = Field(
        default=None,
        max_length=100,
    )

    approval_status: ApprovalStatus | None = None

    notes: str | None = None


class FieldGovernanceMetadataRead(BaseModel):
    id: uuid.UUID
    data_field_id: uuid.UUID

    business_name: str | None
    business_definition: str | None
    department: str | None
    data_owner: str | None
    data_steward: str | None
    business_process: str | None
    system_of_record: str | None

    is_cde: bool
    classification: str | None
    approval_status: str
    notes: str | None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class FieldGovernanceMetadataView(BaseModel):
    id: uuid.UUID | None = None
    data_field_id: uuid.UUID

    business_name: str | None = None
    business_definition: str | None = None
    department: str | None = None
    data_owner: str | None = None
    data_steward: str | None = None
    business_process: str | None = None
    system_of_record: str | None = None

    is_cde: bool = False
    classification: str | None = None
    approval_status: ApprovalStatus = "draft"
    notes: str | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )