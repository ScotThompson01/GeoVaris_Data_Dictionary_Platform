import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ClientRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
