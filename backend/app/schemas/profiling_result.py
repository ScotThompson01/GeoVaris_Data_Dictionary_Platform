import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProfilingResultRead(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    data_field_id: uuid.UUID

    row_count: int
    null_count: int
    null_percentage: Decimal

    distinct_count: int
    distinct_percentage: Decimal

    minimum_value: str | None
    maximum_value: str | None

    minimum_length: int | None
    maximum_length: int | None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)