"""Offline tests for protected-start workload identity under row locks."""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.services import data_quality_execution_protected_start as start


def make_workload():
    project_id = uuid4()
    execution_id = uuid4()
    rule_id = uuid4()
    source_id = uuid4()
    ownership_id = uuid4()

    installation_control = SimpleNamespace(id=uuid4())
    source_control = SimpleNamespace(id=uuid4())

    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
    )

    ownership = SimpleNamespace(
        id=ownership_id,
        execution_id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        data_source_id=source_id,
        ownership_state="reserved",
    )

    reservations = [
        SimpleNamespace(
            id=uuid4(),
            ownership_id=ownership_id,
            reservation_scope="installation",
            capacity_control_id=installation_control.id,
            reservation_state="reserved",
        ),
        SimpleNamespace(
            id=uuid4(),
            ownership_id=ownership_id,
            reservation_scope="source",
            capacity_control_id=source_control.id,
            reservation_state="reserved",
        ),
    ]

    db = Mock()
    db.scalar.return_value = ownership
    db.scalars.return_value.all.return_value = reservations

    arguments = {
        "execution": execution,
        "project_id": project_id,
        "execution_id": execution_id,
        "expected_source_id": source_id,
        "installation_control": installation_control,
        "source_control": source_control,
    }

    return db, ownership, reservations, arguments


def validate(db, arguments, monkeypatch):
    monkeypatch.setattr(
        start,
        "validate_protected_workload",
        Mock(),
    )
    return start._validate_locked_protected_workload(
        db,
        **arguments,
    )


def test_valid_workload_uses_refreshed_row_locks(monkeypatch):
    db, _, _, arguments = make_workload()

    validate(db, arguments, monkeypatch)

    db.scalar.assert_called_once()
    db.scalars.assert_called_once()

    ownership_query = db.scalar.call_args.args[0]
    reservation_query = db.scalars.call_args.args[0]

    assert ownership_query._for_update_arg is not None
    assert reservation_query._for_update_arg is not None

    assert ownership_query.get_execution_options()["populate_existing"] is True
    assert reservation_query.get_execution_options()["populate_existing"] is True

    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_stale_source_locator_is_rejected(monkeypatch):
    db, ownership, _, arguments = make_workload()
    ownership.data_source_id = uuid4()

    with pytest.raises(ValueError, match="ownership source mismatch"):
        validate(db, arguments, monkeypatch)

    db.scalars.assert_not_called()


@pytest.mark.parametrize(
    "scope",
    ["installation", "source"],
)
def test_mismatched_capacity_control_is_rejected(monkeypatch, scope):
    db, _, reservations, arguments = make_workload()

    for reservation in reservations:
        if reservation.reservation_scope == scope:
            reservation.capacity_control_id = uuid4()

    with pytest.raises(ValueError, match="capacity control mismatch"):
        validate(db, arguments, monkeypatch)

    db.commit.assert_not_called()
    db.rollback.assert_not_called()
