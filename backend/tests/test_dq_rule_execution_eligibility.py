"""Tests for Data Quality rule execution eligibility."""

from types import SimpleNamespace

import pytest

from app.services.data_quality_rule_execution import validate_execution_eligibility


def make_rule(status="active", active_version_id="version-1"):
    return SimpleNamespace(
        id="rule-1",
        status=status,
        active_version_id=active_version_id,
    )


def make_version(status="approved", rule_type="range"):
    return SimpleNamespace(
        id="version-1",
        rule_id="rule-1",
        status=status,
        rule_type=rule_type,
        quality_dimension="validity",
    )


def make_field(normalized_data_type="decimal"):
    return SimpleNamespace(normalized_data_type=normalized_data_type)


def test_active_approved_numeric_range_is_eligible():
    validate_execution_eligibility(
        make_rule(),
        make_version(),
        make_field(),
    )


@pytest.mark.parametrize("rule_status", ["draft", "retired"])
def test_inactive_rule_is_rejected(rule_status):
    with pytest.raises(ValueError, match="Rule must be active"):
        validate_execution_eligibility(
            make_rule(status=rule_status),
            make_version(),
            make_field(),
        )


@pytest.mark.parametrize("version_status", ["draft", "retired"])
def test_unapproved_version_is_rejected(version_status):
    with pytest.raises(ValueError, match="approved"):
        validate_execution_eligibility(
            make_rule(),
            make_version(status=version_status),
            make_field(),
        )


def test_version_must_be_active_version():
    with pytest.raises(ValueError, match="active version"):
        validate_execution_eligibility(
            make_rule(active_version_id="different-version"),
            make_version(),
            make_field(),
        )


@pytest.mark.parametrize("data_type", ["string", "date", "boolean", None])
def test_non_numeric_field_is_rejected(data_type):
    with pytest.raises(ValueError, match="numeric"):
        validate_execution_eligibility(
            make_rule(),
            make_version(),
            make_field(normalized_data_type=data_type),
        )


@pytest.mark.parametrize("data_type", ["integer", "decimal"])
def test_numeric_field_types_are_supported(data_type):
    validate_execution_eligibility(
        make_rule(),
        make_version(),
        make_field(normalized_data_type=data_type),
    )


def test_unsupported_rule_type_is_rejected():
    with pytest.raises(ValueError, match="range"):
        validate_execution_eligibility(
            make_rule(),
            make_version(rule_type="regex"),
            make_field(),
        )


def test_version_belonging_to_another_rule_is_rejected():
    rule = make_rule()
    rule.id = "rule-1"

    version = make_version()
    version.rule_id = "different-rule"

    with pytest.raises(ValueError, match="parent rule"):
        validate_execution_eligibility(
            rule,
            version,
            make_field(),
        )
