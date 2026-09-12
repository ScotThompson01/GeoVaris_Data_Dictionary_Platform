import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    client_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: str = Field(default="active", max_length=50)


class ProjectRead(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
