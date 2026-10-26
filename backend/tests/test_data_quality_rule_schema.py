"""Tests for Phase 5 draft Data Quality range rule validation."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.data_quality_rule import RangeRuleDraft


def valid_rule(**overrides):
    values = {
        "rule_name": "Approved Latitude Range",
        "min_value": "24.3",
        "max_value": "31.1",
        "null_allowed": False,
    }
    values.update(overrides)
    return values


def test_valid_range_rule():
    rule = RangeRuleDraft.model_validate(valid_rule())

    assert rule.min_value == Decimal("24.3")
    assert rule.max_value == Decimal("31.1")
    assert rule.rule_type == "range"
    assert rule.quality_dimension == "validity"
    assert rule.status == "draft"
    assert rule.null_allowed is False


def test_equal_range_boundaries_are_allowed():
    rule = RangeRuleDraft.model_validate(
        valid_rule(min_value="25", max_value="25")
    )

    assert rule.min_value == rule.max_value


def test_reversed_range_is_rejected():
    with pytest.raises(ValidationError, match="Minimum value"):
        RangeRuleDraft.model_validate(
            valid_rule(min_value="31.1", max_value="24.3")
        )


@pytest.mark.parametrize("boundary", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_boundaries_are_rejected(boundary):
    with pytest.raises(ValidationError, match="finite number"):
        RangeRuleDraft.model_validate(valid_rule(min_value=boundary))


def test_unsupported_rule_type_is_rejected():
    with pytest.raises(ValidationError):
        RangeRuleDraft.model_validate(valid_rule(rule_type="regex"))


def test_non_draft_status_is_rejected():
    with pytest.raises(ValidationError):
        RangeRuleDraft.model_validate(valid_rule(status="published"))


def test_unexpected_properties_are_rejected():
    with pytest.raises(ValidationError):
        RangeRuleDraft.model_validate(valid_rule(execute_now=True))


def test_missing_rule_name_is_rejected():
    with pytest.raises(ValidationError):
        RangeRuleDraft.model_validate(valid_rule(rule_name=""))

def test_range_boundaries_respect_database_precision():
    rule = RangeRuleDraft.model_validate(
        valid_rule(
            min_value="0",
            max_value="12345678901234.1234567890",
        )
    )

    assert rule.max_value == Decimal("12345678901234.1234567890")


@pytest.mark.parametrize(
    "boundary",
    [
        "123456789012345.1234567890",
        "1.12345678901",
        "999999999999999.0",
    ],
)
def test_range_boundaries_exceeding_database_precision_are_rejected(boundary):
    with pytest.raises(ValidationError):
        RangeRuleDraft.model_validate(
            valid_rule(min_value="0", max_value=boundary)
        )
