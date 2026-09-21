"""Request and response schemas for local authentication."""

from uuid import UUID

from pydantic import BaseModel, Field


class SignInRequest(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1)


class SignInResponse(BaseModel):
    session_token: str
    user_id: UUID
    username: str


class CurrentUserResponse(BaseModel):
    user_id: UUID
    username: str

class LogoutRequest(BaseModel):
    session_token: str = Field(min_length=1)