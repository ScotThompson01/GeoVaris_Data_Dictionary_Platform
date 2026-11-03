"""Phase 5E tests for staging pending execution records.

No database or client source connections are required.
"""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.services.data_quality_execution_persistence import (
    stage_pending_execution,
)


def _prepared():
    rule_id = uuid4()
    return {
        "rule": SimpleNamespace(id=rule_id),
        "version": SimpleNamespace(id=uuid4(), rule_id=rule_id),
    }


def test_pending_execution_stages_identity_without_measurements():
    db = Mock()
    prepared = _prepared()
    project_id = uuid4()
    actor_user_id = uuid4()

    execution = stage_pending_execution(
        db,
        prepared=prepared,
        project_id=project_id,
        actor_user_id=actor_user_id,
    )

    assert execution.project_id == project_id
    assert execution.actor_user_id == actor_user_id
    assert execution.rule_id == prepared["rule"].id
    assert execution.version_id == prepared["version"].id
    assert execution.status == "pending"
    assert execution.total_count is None
    assert execution.passing_count is None
    assert execution.violation_count is None
    assert execution.error_code is None
    assert execution.started_at is None
    assert execution.completed_at is None

    db.add.assert_called_once_with(execution)
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()


def test_pending_execution_rejects_mismatched_rule_version():
    db = Mock()
    prepared = _prepared()
    prepared["version"].rule_id = uuid4()

    with pytest.raises(ValueError, match="does not belong"):
        stage_pending_execution(
            db,
            prepared=prepared,
            project_id=uuid4(),
            actor_user_id=uuid4(),
        )

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("invalid_identity", [None, "", "not-a-uuid"])
def test_pending_execution_rejects_invalid_project_identity(invalid_identity):
    db = Mock()

    with pytest.raises(ValueError, match="project"):
        stage_pending_execution(
            db,
            prepared=_prepared(),
            project_id=invalid_identity,
            actor_user_id=uuid4(),
        )

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_pending_execution_rejects_invalid_actor_identity():
    db = Mock()

    with pytest.raises(ValueError, match="actor"):
        stage_pending_execution(
            db,
            prepared=_prepared(),
            project_id=uuid4(),
            actor_user_id=None,
        )

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "invalid_identity",
    [None, "", "not-a-uuid"],
)
def test_pending_execution_rejects_invalid_rule_identity(invalid_identity):
    db = Mock()
    prepared = _prepared()
    prepared["rule"].id = invalid_identity

    with pytest.raises(ValueError, match="rule identity"):
        stage_pending_execution(
            db,
            prepared=prepared,
            project_id=uuid4(),
            actor_user_id=uuid4(),
        )

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "invalid_identity",
    [None, "", "not-a-uuid"],
)
def test_pending_execution_rejects_invalid_version_identity(invalid_identity):
    db = Mock()
    prepared = _prepared()
    prepared["version"].id = invalid_identity

    with pytest.raises(ValueError, match="rule version identity"):
        stage_pending_execution(
            db,
            prepared=prepared,
            project_id=uuid4(),
            actor_user_id=uuid4(),
        )

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


from datetime import datetime, timezone

from app.services.data_quality_execution_persistence import (
    stage_running_execution,
)


def test_pending_execution_can_transition_to_running():
    db = Mock()
    execution = SimpleNamespace(
        status="pending",
        started_at=None,
        completed_at=None,
        total_count=None,
        passing_count=None,
        violation_count=None,
    )
    started_at = datetime(2026, 11, 3, 14, 0, tzinfo=timezone.utc)

    result = stage_running_execution(
        db,
        execution=execution,
        started_at=started_at,
    )

    assert result is execution
    assert execution.status == "running"
    assert execution.started_at == started_at
    assert execution.completed_at is None
    assert execution.total_count is None
    assert execution.passing_count is None
    assert execution.violation_count is None
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "status",
    ["running", "succeeded", "failed", "incomplete",
     "status_uncertain", "cancelled"],
)
def test_only_pending_execution_can_start(status):
    db = Mock()
    execution = SimpleNamespace(
        status=status,
        started_at=None,
        completed_at=None,
        total_count=None,
        passing_count=None,
        violation_count=None,
    )

    with pytest.raises(ValueError):
        stage_running_execution(
            db,
            execution=execution,
            started_at=datetime.now(timezone.utc),
        )

    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_running_transition_rejects_naive_start_timestamp():
    db = Mock()
    execution = SimpleNamespace(
        status="pending",
        started_at=None,
        completed_at=None,
        total_count=None,
        passing_count=None,
        violation_count=None,
    )

    with pytest.raises(ValueError, match="timezone"):
        stage_running_execution(
            db,
            execution=execution,
            started_at=datetime(2026, 11, 3, 14, 0),
        )

    assert execution.status == "pending"
    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_running_transition_rejects_existing_measurements():
    db = Mock()
    execution = SimpleNamespace(
        status="pending",
        started_at=None,
        completed_at=None,
        total_count=10,
        passing_count=None,
        violation_count=None,
    )

    with pytest.raises(ValueError):
        stage_running_execution(
            db,
            execution=execution,
            started_at=datetime.now(timezone.utc),
        )

    assert execution.status == "pending"
    db.flush.assert_not_called()
    db.commit.assert_not_called()
