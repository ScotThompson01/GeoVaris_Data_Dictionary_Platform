"""API schemas for project-level Administration settings."""

import uuid

from pydantic import BaseModel, ConfigDict, StrictBool


class ProjectSettingsRead(BaseModel):
    project_id: uuid.UUID
    allow_steward_self_approval: bool

    model_config = ConfigDict(from_attributes=True)


class ProjectSettingsUpdate(BaseModel):
    allow_steward_self_approval: StrictBool

    model_config = ConfigDict(extra="forbid")
