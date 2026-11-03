"""Regression tests for Phase 5E admission configuration."""

import pytest

from app.core.config import Settings
from app.services.data_quality_execution_capacity_policy import (
    ExecutionCapacityPolicyError,
    require_execution_capacity_configuration,
)


def test_execution_admission_defaults_to_disabled(monkeypatch):
    monkeypatch.delenv("DQ_EXECUTION_ADMISSION_ENABLED", raising=False)
    monkeypatch.delenv("DQ_EXECUTION_MAX_CONCURRENT", raising=False)

    config = Settings(
        _env_file=None,
        database_url="postgresql://unused:unused@localhost/unused",
    )

    assert config.dq_execution_admission_enabled is False
    assert config.dq_execution_max_concurrent == 0

    with pytest.raises(ExecutionCapacityPolicyError):
        require_execution_capacity_configuration(config)


def test_enabled_admission_still_requires_positive_capacity():
    config = Settings(
        _env_file=None,
        database_url="postgresql://unused:unused@localhost/unused",
        dq_execution_admission_enabled=True,
        dq_execution_max_concurrent=0,
    )

    with pytest.raises(
        ExecutionCapacityPolicyError,
        match="positive integer",
    ):
        require_execution_capacity_configuration(config)


def test_explicit_valid_capacity_policy_configuration():
    config = Settings(
        _env_file=None,
        database_url="postgresql://unused:unused@localhost/unused",
        dq_execution_admission_enabled=True,
        dq_execution_max_concurrent=2,
    )

    assert require_execution_capacity_configuration(config) == 2
