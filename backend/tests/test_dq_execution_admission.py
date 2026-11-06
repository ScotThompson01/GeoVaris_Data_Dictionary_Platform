"""Fail-closed tests for internal Phase 5E execution admission.

These tests do not connect to source systems or databases.
Production admission remains disabled.
"""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core.config import settings
from app.services.data_quality_execution_capacity_policy import (
    ExecutionCapacityPolicyError,
)


def prepared_execution():
    rule_id = uuid4()
    return {
        "rule": SimpleNamespace(id=rule_id),
        "version": SimpleNamespace(
            id=uuid4(),
            rule_id=rule_id,
        ),
        "field": SimpleNamespace(id=uuid4()),
        "source_object": SimpleNamespace(id=uuid4()),
        "source": SimpleNamespace(id=uuid4()),
    }


def test_disabled_admission_rejects_before_database_access():
    from app.services.data_quality_execution_admission import (
        stage_protected_execution_admission,
    )

    assert settings.dq_execution_admission_enabled is False

    db = Mock()

    with pytest.raises(
        ExecutionCapacityPolicyError,
        match="admission is disabled",
    ):
        stage_protected_execution_admission(
            db,
            prepared=prepared_execution(),
            project_id=uuid4(),
            actor_user_id=uuid4(),
        )

    db.scalar.assert_not_called()
    db.scalars.assert_not_called()
    db.execute.assert_not_called()
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_disabled_admission_never_creates_workload_records():
    from app.services.data_quality_execution_admission import (
        stage_protected_execution_admission,
    )

    assert settings.dq_execution_admission_enabled is False

    db = Mock()
    prepared = prepared_execution()

    with pytest.raises(ExecutionCapacityPolicyError):
        stage_protected_execution_admission(
            db,
            prepared=prepared,
            project_id=uuid4(),
            actor_user_id=uuid4(),
        )

    assert db.mock_calls == []


def test_enabled_configuration_still_rejects_unimplemented_admission(
    monkeypatch,
):
    from app.services import data_quality_execution_admission as admission

    enabled = SimpleNamespace(
        dq_execution_admission_enabled=True,
        dq_execution_max_concurrent=2,
    )
    monkeypatch.setattr(admission, "settings", enabled)

    db = Mock()

    with pytest.raises(
        ExecutionCapacityPolicyError,
        match="not yet implemented",
    ):
        admission.stage_protected_execution_admission(
            db,
            prepared=prepared_execution(),
            project_id=uuid4(),
            actor_user_id=uuid4(),
        )

    assert db.mock_calls == []


@pytest.mark.parametrize("limit", [0, -1, None, True, "2"])
def test_enabled_admission_rejects_invalid_capacity_before_database_access(
    monkeypatch, limit
):
    from app.services import data_quality_execution_admission as admission

    configuration = SimpleNamespace(
        dq_execution_admission_enabled=True,
        dq_execution_max_concurrent=limit,
    )
    monkeypatch.setattr(admission, "settings", configuration)

    db = Mock()

    with pytest.raises(ExecutionCapacityPolicyError):
        admission.stage_protected_execution_admission(
            db,
            prepared=prepared_execution(),
            project_id=uuid4(),
            actor_user_id=uuid4(),
        )

    assert db.mock_calls == []
