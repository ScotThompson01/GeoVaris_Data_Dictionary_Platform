"""Validation schemas for client-scoped governance assignments."""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


GovernanceRole = Literal[
    "executive_accountable_owner",
    "department_data_owner",
    "data_steward",
]


class GovernanceAssignmentCreate(BaseModel):
    person_id: uuid.UUID
    department_id: uuid.UUID
    role: GovernanceRole
    effective_start: date | None = None
    effective_end: date | None = None

    @model_validator(mode="after")
    def validate_effective_dates(self):
        if (
            self.effective_start is not None
            and self.effective_end is not None
            and self.effective_end < self.effective_start
        ):
            raise ValueError(
                "Effective end date cannot precede effective start date."
            )
        return self


class GovernanceAssignmentRead(GovernanceAssignmentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    is_active: bool
