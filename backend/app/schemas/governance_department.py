"""Request and response schemas for Governance Departments."""

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GovernanceDepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        name = value.strip()

        if not name:
            raise ValueError("Department name cannot be blank.")

        return name


class GovernanceDepartmentRead(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    name: str
    description: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
