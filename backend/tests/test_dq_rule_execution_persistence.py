"""Isolated tests for Data Quality execution-history persistence."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.services.data_quality_rule_execution import record_successful_execution


def test_successful_execution_records_aggregates_without_committing():
    db = Mock()
    project_id = uuid4()
    actor_user_id = uuid4()
    rule_id = uuid4()
    version_id = uuid4()

    started_at = datetime(2026, 10, 29, 14, 0, tzinfo=timezone.utc)
    completed_at = datetime(2026, 10, 29, 14, 1, tzinfo=timezone.utc)

    prepared = {
        "rule": SimpleNamespace(id=rule_id),
        "version": SimpleNamespace(id=version_id, rule_id=rule_id),
    }
    measurement = SimpleNamespace(
        total_count=100,
        passing_count=95,
        violation_count=5,
    )

    execution = record_successful_execution(
        db,
        prepared=prepared,
        project_id=project_id,
        actor_user_id=actor_user_id,
        measurement=measurement,
        started_at=started_at,
        completed_at=completed_at,
    )

    assert execution.project_id == project_id
    assert execution.actor_user_id == actor_user_id
    assert execution.rule_id == rule_id
    assert execution.version_id == version_id
    assert execution.status == "succeeded"
    assert execution.total_count == 100
    assert execution.passing_count == 95
    assert execution.violation_count == 5
    assert execution.error_code is None
    assert execution.started_at == started_at
    assert execution.completed_at == completed_at

    db.add.assert_called_once_with(execution)
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()


def test_successful_execution_rejects_inconsistent_counts():
    import pytest

    db = Mock()
    rule_id = uuid4()
    prepared = {
        "rule": SimpleNamespace(id=rule_id),
        "version": SimpleNamespace(id=uuid4(), rule_id=rule_id),
    }
    measurement = SimpleNamespace(
        total_count=100,
        passing_count=95,
        violation_count=10,
    )
    now = datetime.now(timezone.utc)

    with pytest.raises(ValueError, match="counts must balance"):
        record_successful_execution(
            db,
            prepared=prepared,
            project_id=uuid4(),
            actor_user_id=uuid4(),
            measurement=measurement,
            started_at=now,
            completed_at=now,
        )

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_successful_execution_rejects_mismatched_rule_version():
    import pytest

    db = Mock()
    prepared = {
        "rule": SimpleNamespace(id=uuid4()),
        "version": SimpleNamespace(id=uuid4(), rule_id=uuid4()),
    }
    measurement = SimpleNamespace(
        total_count=100,
        passing_count=95,
        violation_count=5,
    )
    now = datetime.now(timezone.utc)

    with pytest.raises(ValueError, match="does not belong to the rule"):
        record_successful_execution(
            db,
            prepared=prepared,
            project_id=uuid4(),
            actor_user_id=uuid4(),
            measurement=measurement,
            started_at=now,
            completed_at=now,
        )

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_successful_execution_rejects_completion_before_start():
    import pytest
    from datetime import timedelta

    db = Mock()
    rule_id = uuid4()
    prepared = {
        "rule": SimpleNamespace(id=rule_id),
        "version": SimpleNamespace(id=uuid4(), rule_id=rule_id),
    }
    measurement = SimpleNamespace(
        total_count=100,
        passing_count=95,
        violation_count=5,
    )

    started_at = datetime.now(timezone.utc)
    completed_at = started_at - timedelta(seconds=1)

    with pytest.raises(ValueError, match="cannot precede its start"):
        record_successful_execution(
            db,
            prepared=prepared,
            project_id=uuid4(),
            actor_user_id=uuid4(),
            measurement=measurement,
            started_at=started_at,
            completed_at=completed_at,
        )

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_successful_execution_rejects_invalid_count_types():
    import pytest

    rule_id = uuid4()
    prepared = {
        "rule": SimpleNamespace(id=rule_id),
        "version": SimpleNamespace(id=uuid4(), rule_id=rule_id),
    }
    now = datetime.now(timezone.utc)

    invalid_measurements = [
        (-1, 0, 0),
        (100, -1, 101),
        (100, 95.5, 4.5),
        (True, 1, 0),
    ]

    for total, passing, violations in invalid_measurements:
        db = Mock()
        measurement = SimpleNamespace(
            total_count=total,
            passing_count=passing,
            violation_count=violations,
        )

        with pytest.raises(ValueError, match="nonnegative integers"):
            record_successful_execution(
                db,
                prepared=prepared,
                project_id=uuid4(),
                actor_user_id=uuid4(),
                measurement=measurement,
                started_at=now,
                completed_at=now,
            )

        db.add.assert_not_called()
        db.flush.assert_not_called()
        db.commit.assert_not_called()
