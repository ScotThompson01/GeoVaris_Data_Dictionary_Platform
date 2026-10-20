"""Request and response schemas for Governance People."""

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GovernancePersonCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    job_title: str | None = Field(default=None, max_length=255)
    business_email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    contact_url: str | None = Field(default=None, max_length=1000)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Full name cannot be blank.")
        return name

    @field_validator("job_title", "business_email", "phone", "contact_url")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("business_email")
    @classmethod
    def validate_business_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if (
            "@" not in value
            or value.startswith("@")
            or value.endswith("@")
            or any(character.isspace() for character in value)
        ):
            raise ValueError("Enter a valid business email address.")
        return value

    @field_validator("contact_url")
    @classmethod
    def validate_contact_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.startswith("https://"):
            raise ValueError("Contact URL must use HTTPS.")
        return value


class GovernancePersonRead(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    full_name: str
    job_title: str | None
    business_email: str | None
    phone: str | None
    contact_url: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
