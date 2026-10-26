"""Tests for Data Quality rule retrieval response schemas."""

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.data_quality_rule import (
    RangeRuleRead,
    RangeRuleVersionRead,
)


def test_draft_rule_with_version_history():
    rule_id = uuid.uuid4()
    field_id = uuid.uuid4()
    version_id = uuid.uuid4()

    result = RangeRuleRead(
        rule_id=rule_id,
        data_field_id=field_id,
        rule_name="Latitude Range",
        status="draft",
        active_version_id=None,
        versions=[
            RangeRuleVersionRead(
                version_id=version_id,
                version_number=1,
                rule_type="range",
                quality_dimension="validity",
                min_value=Decimal("-90"),
                max_value=Decimal("90"),
                null_allowed=False,
                status="draft",
            )
        ],
    )

    assert result.rule_id == rule_id
    assert result.active_version_id is None
    assert len(result.versions) == 1
    assert result.versions[0].version_number == 1
    assert result.versions[0].min_value == Decimal("-90")
    assert result.versions[0].max_value == Decimal("90")
    assert result.versions[0].status == "draft"


def test_retrieval_schema_rejects_invalid_status():
    with pytest.raises(ValidationError):
        RangeRuleRead(
            rule_id=uuid.uuid4(),
            data_field_id=uuid.uuid4(),
            rule_name="Latitude Range",
            status="published",
            active_version_id=None,
            versions=[],
        )


def test_retrieval_schema_rejects_unexpected_fields():
    with pytest.raises(ValidationError):
        RangeRuleVersionRead(
            version_id=uuid.uuid4(),
            version_number=1,
            rule_type="range",
            quality_dimension="validity",
            min_value=Decimal("-90"),
            max_value=Decimal("90"),
            null_allowed=False,
            status="draft",
            unexpected_field="not allowed",
        )
