"""Structured validation for Phase 5 draft Data Quality range rules."""

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RangeRuleDraft(BaseModel):
    """A proposed numeric range standard; not an executable rule."""

    model_config = ConfigDict(extra="forbid")

    rule_name: str = Field(min_length=1, max_length=255)
    rule_type: Literal["range"] = "range"
    quality_dimension: Literal["validity"] = "validity"

    min_value: Decimal = Field(max_digits=24, decimal_places=10)
    max_value: Decimal = Field(max_digits=24, decimal_places=10)
    null_allowed: bool = True

    status: Literal["draft"] = "draft"

    @model_validator(mode="after")
    def validate_range(self) -> "RangeRuleDraft":
        if not self.min_value.is_finite() or not self.max_value.is_finite():
            raise ValueError("Range boundaries must be finite numbers.")

        if self.min_value > self.max_value:
            raise ValueError(
                "Minimum value cannot exceed maximum value."
            )

        return self


class RangeRuleCreate(RangeRuleDraft):
    """Request to create a draft range rule for an existing data field."""

    data_field_id: uuid.UUID



class RangeRuleCreateResponse(BaseModel):
    """Result of creating an unapproved, inactive range rule."""

    model_config = ConfigDict(extra="forbid")

    rule_id: uuid.UUID
    version_id: uuid.UUID
    data_field_id: uuid.UUID
    version_number: Literal[1] = 1
    rule_status: Literal["draft"] = "draft"
    version_status: Literal["draft"] = "draft"
    active_version_id: None = None


class RangeRuleVersionRead(BaseModel):
    """A stored version of a Data Quality range rule."""

    model_config = ConfigDict(extra="forbid")

    version_id: uuid.UUID
    version_number: int
    rule_type: Literal["range"]
    quality_dimension: Literal["validity"]
    min_value: Decimal
    max_value: Decimal
    null_allowed: bool
    status: Literal["draft", "approved", "retired"]


class RangeRuleRead(BaseModel):
    """A Data Quality rule and its version history."""

    model_config = ConfigDict(extra="forbid")

    rule_id: uuid.UUID
    data_field_id: uuid.UUID
    rule_name: str
    status: Literal["draft", "active", "retired"]
    active_version_id: uuid.UUID | None
    versions: list[RangeRuleVersionRead]
