"""Offline tests for the PostgreSQL profiling deployment gate."""

from types import SimpleNamespace

import pytest

from app.services.postgresql_profiling_execution_policy import (
    PostgreSQLProfilingExecutionDisabledError,
    require_postgresql_profiling_execution_enabled,
)


def test_profiling_execution_defaults_to_disabled():
    from app.core.config import Settings

    assert (
        Settings.model_fields[
            "postgresql_profiling_execution_enabled"
        ].default
        is False
    )


@pytest.mark.parametrize("enabled", [False, None, 0, "true"])
def test_profiling_execution_rejects_non_boolean_true(enabled):
    settings = SimpleNamespace(
        postgresql_profiling_execution_enabled=enabled
    )

    with pytest.raises(
        PostgreSQLProfilingExecutionDisabledError,
        match="profiling execution is disabled",
    ):
        require_postgresql_profiling_execution_enabled(settings)


def test_explicit_true_passes_only_the_deployment_gate():
    settings = SimpleNamespace(
        postgresql_profiling_execution_enabled=True
    )

    assert require_postgresql_profiling_execution_enabled(settings) is None
