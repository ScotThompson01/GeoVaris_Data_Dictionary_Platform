"""Request and response schemas for installation administrator user management."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CreateManagedUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=12)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not all(
            character.isascii()
            and (character.isalnum() or character in "._-")
            for character in value
        ):
            raise ValueError(
                "Username may contain only ASCII letters, numbers, ., _ and -."
            )
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 1024:
            raise ValueError("Password must not exceed 1024 UTF-8 bytes.")
        return value


class ManagedUserResponse(BaseModel):
    user_id: UUID
    username: str
    is_active: bool
    is_installation_admin: bool
    created_at: datetime
    updated_at: datetime


class UpdateManagedUserRoleRequest(BaseModel):
    is_installation_admin: bool
