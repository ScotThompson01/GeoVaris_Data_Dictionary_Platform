"""Tests for staging a successful outcome on an existing execution.

This is a mutation primitive, NOT authorization to complete execution.
A future coordinator must independently lock and validate protection
and revalidate the source connection before calling it.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.services.data_quality_execution_persistence import (
    stage_successful_execution_outcome,
)


def make_execution(status="running"):
    started_at = datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        rule_id=uuid4(),
        status=status,
        started_at=started_at,
        completed_at=None,
        total_count=None,
        passing_count=None,
        violation_count=None,
        error_code=None,
    )


def make_measurement(total=100, passing=95, violations=5):
    return SimpleNamespace(
        total_count=total,
        passing_count=passing,
        violation_count=violations,
    )


def test_success_updates_same_execution_without_inserting_or_committing():
    db = Mock()
    execution = make_execution()
    execution_id = execution.id
    completed_at = execution.started_at + timedelta(seconds=10)

    result = stage_successful_execution_outcome(
        db,
        execution=execution,
        measurement=make_measurement(),
        completed_at=completed_at,
    )

    assert result is execution
    assert execution.id == execution_id
    assert execution.status == "succeeded"
    assert execution.total_count == 100
    assert execution.passing_count == 95
    assert execution.violation_count == 5
    assert execution.completed_at == completed_at
    assert execution.error_code is None
    db.flush.assert_called_once_with()
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()


@pytest.mark.parametrize(
    "status",
    ["pending", "succeeded", "failed", "status_uncertain", "cancelled"],
)
def test_non_running_execution_cannot_be_completed(status):
    db = Mock()
    execution = make_execution(status=status)

    with pytest.raises(ValueError):
        stage_successful_execution_outcome(
            db,
            execution=execution,
            measurement=make_measurement(),
            completed_at=execution.started_at + timedelta(seconds=10),
        )

    assert execution.status == status
    assert execution.completed_at is None
    assert execution.total_count is None
    db.flush.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    ("total", "passing", "violations"),
    [
        (100, 94, 5),
        (-1, 0, 0),
        (100, 100, -1),
        (True, 0, 0),
        (10.0, 5, 5),
    ],
)
def test_invalid_aggregates_rejected_without_partial_mutation(
    total, passing, violations
):
    db = Mock()
    execution = make_execution()

    with pytest.raises(ValueError):
        stage_successful_execution_outcome(
            db,
            execution=execution,
            measurement=make_measurement(total, passing, violations),
            completed_at=execution.started_at + timedelta(seconds=10),
        )

    assert execution.status == "running"
    assert execution.completed_at is None
    assert execution.total_count is None
    db.flush.assert_not_called()


def test_completion_before_start_is_rejected():
    db = Mock()
    execution = make_execution()

    with pytest.raises(ValueError):
        stage_successful_execution_outcome(
            db,
            execution=execution,
            measurement=make_measurement(),
            completed_at=execution.started_at - timedelta(seconds=1),
        )

    assert execution.status == "running"
    db.flush.assert_not_called()


def test_naive_completion_timestamp_is_rejected():
    db = Mock()
    execution = make_execution()

    with pytest.raises(ValueError):
        stage_successful_execution_outcome(
            db,
            execution=execution,
            measurement=make_measurement(),
            completed_at=datetime(2026, 11, 9, 15, 0),
        )

    assert execution.status == "running"
    db.flush.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("total_count", 10),
        ("passing_count", 9),
        ("violation_count", 1),
        ("error_code", "PREVIOUS_ERROR"),
        ("completed_at", datetime(2026, 11, 9, 15, 1, tzinfo=timezone.utc)),
    ],
)
def test_existing_outcome_data_cannot_be_overwritten(field, value):
    db = Mock()
    execution = make_execution()
    setattr(execution, field, value)

    with pytest.raises(ValueError):
        stage_successful_execution_outcome(
            db,
            execution=execution,
            measurement=make_measurement(),
            completed_at=execution.started_at + timedelta(seconds=10),
        )

    assert execution.status == "running"
    assert getattr(execution, field) == value
    db.flush.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "started_at",
    [
        None,
        datetime(2026, 11, 9, 15, 0),
        "2026-11-09T15:00:00Z",
    ],
)
def test_missing_or_invalid_start_timestamp_rejected(started_at):
    db = Mock()
    execution = make_execution()
    execution.started_at = started_at

    with pytest.raises(ValueError):
        stage_successful_execution_outcome(
            db,
            execution=execution,
            measurement=make_measurement(),
            completed_at=datetime(
                2026, 11, 9, 15, 1, tzinfo=timezone.utc
            ),
        )

    assert execution.status == "running"
    assert execution.completed_at is None
    assert execution.total_count is None
    db.flush.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()
