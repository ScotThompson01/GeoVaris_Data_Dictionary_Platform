import uuid

from pydantic import BaseModel, Field


class CSVDiscoveryRequest(BaseModel):
    data_source_id: uuid.UUID

    file_name: str = Field(
        min_length=1,
        max_length=255,
    )