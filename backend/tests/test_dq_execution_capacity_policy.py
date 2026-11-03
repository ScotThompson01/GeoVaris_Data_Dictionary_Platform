"""Tests for fail-closed Phase 5E execution-capacity configuration."""

from types import SimpleNamespace

import pytest

from app.services.data_quality_execution_capacity_policy import (
    ExecutionCapacityPolicyError,
    require_execution_capacity_configuration,
)


def make_settings(*, enabled=False, limit=None):
    return SimpleNamespace(
        dq_execution_admission_enabled=enabled,
        dq_execution_max_concurrent=limit,
    )


def test_admission_disabled_by_default():
    with pytest.raises(ExecutionCapacityPolicyError, match="disabled"):
        require_execution_capacity_configuration(make_settings())


def test_missing_limit_rejected():
    with pytest.raises(ExecutionCapacityPolicyError, match="positive integer"):
        require_execution_capacity_configuration(make_settings(enabled=True))


@pytest.mark.parametrize("limit", [0, -1, True, False, 1.5, "2", None])
def test_invalid_limits_rejected(limit):
    with pytest.raises(ExecutionCapacityPolicyError, match="positive integer"):
        require_execution_capacity_configuration(
            make_settings(enabled=True, limit=limit)
        )


@pytest.mark.parametrize("enabled", [1, "true", None])
def test_non_boolean_enable_flags_rejected(enabled):
    with pytest.raises(ExecutionCapacityPolicyError, match="disabled"):
        require_execution_capacity_configuration(
            make_settings(enabled=enabled, limit=2)
        )


@pytest.mark.parametrize("limit", [1, 2, 10])
def test_valid_configuration_returns_installation_limit(limit):
    assert require_execution_capacity_configuration(
        make_settings(enabled=True, limit=limit)
    ) == limit


def test_missing_settings_attributes_fail_closed():
    with pytest.raises(ExecutionCapacityPolicyError, match="disabled"):
        require_execution_capacity_configuration(SimpleNamespace())
