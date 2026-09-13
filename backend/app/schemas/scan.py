import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


ScanType = Literal[
    "metadata",
    "basic_profile",
    "approved_sample",
    "full_profile",
]

ScanStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
]


class ScanCreate(BaseModel):
    data_source_id: uuid.UUID
    scan_type: ScanType = "metadata"
    status: ScanStatus = "pending"
    connector_version: str | None = None


class ScanRead(BaseModel):
    id: uuid.UUID
    data_source_id: uuid.UUID
    scan_type: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    connector_version: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)