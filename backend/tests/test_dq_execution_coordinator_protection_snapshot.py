"""Read-only checks for a protected execution snapshot.

These tests do not prove independent transaction visibility.
The coordinator must open a separate database session for that.
"""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.services.data_quality_execution_coordinator_protection_snapshot import (
    inspect_protected_execution_snapshot,
)


def make_records():
    project_id = uuid4()
    execution_id = uuid4()
    rule_id = uuid4()
    source_id = uuid4()
    ownership_id = uuid4()

    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        status="pending",
    )

    ownership = SimpleNamespace(
        id=ownership_id,
        execution_id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        data_source_id=source_id,
        ownership_state="reserved",
        released_at=None,
        release_actor=None,
        release_reason=None,
        release_evidence_reference=None,
    )

    reservations = [
        SimpleNamespace(
            id=uuid4(),
            ownership_id=ownership_id,
            ownership_data_source_id=source_id,
            data_source_id=reserved_source,
            capacity_control_id=uuid4(),
            reservation_scope=scope,
            reservation_state="reserved",
            released_at=None,
            release_actor=None,
            release_reason=None,
            release_evidence_reference=None,
        )
        for scope, reserved_source in (
            ("installation", None),
            ("source", source_id),
        )
    ]

    return execution, ownership, reservations


def inspect(execution, ownership, reservations, **overrides):
    db = Mock()
    db.scalar.side_effect = [execution, ownership]
    db.scalars.return_value.all.return_value = reservations

    arguments = {
        "project_id": execution.project_id,
        "execution_id": execution.id,
        "expected_status": "pending",
    }
    arguments.update(overrides)

    return db, arguments


def test_valid_protection_snapshot_is_read_only():
    execution, ownership, reservations = make_records()
    db, arguments = inspect(execution, ownership, reservations)

    result = inspect_protected_execution_snapshot(db, **arguments)

    assert result is execution
    assert db.scalar.call_count == 2
    assert db.scalars.call_count == 1
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.add.assert_not_called()
    db.flush.assert_not_called()


def test_running_snapshot_can_be_verified():
    execution, ownership, reservations = make_records()
    execution.status = "running"
    db, arguments = inspect(
        execution, ownership, reservations, expected_status="running"
    )

    assert inspect_protected_execution_snapshot(db, **arguments) is execution


@pytest.mark.parametrize(
    "field",
    ["id", "project_id", "rule_id"],
)
def test_ownership_identity_mismatch_rejected(field):
    execution, ownership, reservations = make_records()
    if field == "id":
        ownership.execution_id = uuid4()
    else:
        setattr(ownership, field, uuid4())

    db, arguments = inspect(execution, ownership, reservations)

    with pytest.raises(ValueError):
        inspect_protected_execution_snapshot(db, **arguments)

    db.commit.assert_not_called()


def test_missing_execution_rejected_without_protection_queries():
    execution, ownership, reservations = make_records()
    db, arguments = inspect(execution, ownership, reservations)
    db.scalar.side_effect = [None]

    with pytest.raises(ValueError):
        inspect_protected_execution_snapshot(db, **arguments)

    assert db.scalar.call_count == 1
    db.scalars.assert_not_called()


def test_missing_ownership_rejected():
    execution, _, reservations = make_records()
    db, arguments = inspect(execution, None, reservations)

    with pytest.raises(ValueError):
        inspect_protected_execution_snapshot(db, **arguments)


def test_missing_source_reservation_rejected():
    execution, ownership, reservations = make_records()
    db, arguments = inspect(execution, ownership, reservations[:1])

    with pytest.raises(ValueError):
        inspect_protected_execution_snapshot(db, **arguments)


def test_released_ownership_rejected():
    execution, ownership, reservations = make_records()
    ownership.ownership_state = "released"
    db, arguments = inspect(execution, ownership, reservations)

    with pytest.raises(ValueError):
        inspect_protected_execution_snapshot(db, **arguments)


def test_wrong_execution_status_rejected():
    execution, ownership, reservations = make_records()
    execution.status = "failed"
    db, arguments = inspect(execution, ownership, reservations)

    with pytest.raises(ValueError):
        inspect_protected_execution_snapshot(db, **arguments)

    db.scalars.assert_not_called()


@pytest.mark.parametrize(
    "invalid",
    [None, "", "cancelled", 1, True],
)
def test_invalid_expected_status_rejected(invalid):
    execution, ownership, reservations = make_records()
    db, arguments = inspect(
        execution, ownership, reservations, expected_status=invalid
    )

    with pytest.raises(ValueError):
        inspect_protected_execution_snapshot(db, **arguments)

    db.scalar.assert_not_called()
