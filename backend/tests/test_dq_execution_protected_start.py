"""Tests for internal Phase 5E protected execution start.

The caller must use a new transaction after committed admission.
These tests do not authorize source work or runtime admission.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.services import data_quality_execution_protected_start as start


def fixture():
    project_id = uuid4()
    rule_id = uuid4()
    source_id = uuid4()
    execution_id = uuid4()
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
            data_source_id=reservation_source,
            capacity_control_id=uuid4(),
            reservation_scope=scope,
            reservation_state="reserved",
            released_at=None,
            release_actor=None,
            release_reason=None,
            release_evidence_reference=None,
        )
        for scope, reservation_source in (
            ("installation", None),
            ("source", source_id),
        )
    ]
    return execution, ownership, reservations


def setup_mocks(monkeypatch, execution, ownership, reservations):
    installation = SimpleNamespace(id=uuid4())
    source = SimpleNamespace(id=uuid4())

    for reservation in reservations:
        if reservation.reservation_scope == "installation":
            reservation.capacity_control_id = installation.id
        elif reservation.reservation_scope == "source":
            reservation.capacity_control_id = source.id

    source_id = (
        ownership.data_source_id
        if ownership is not None
        else next(
            (
                reservation.ownership_data_source_id
                for reservation in reservations
            ),
            uuid4(),
        )
    )

    authorize = Mock(
        return_value=(execution, source_id, installation, source)
    )
    transition = Mock(return_value=execution)

    monkeypatch.setattr(
        start, "_lock_authorized_protected_start", authorize
    )
    monkeypatch.setattr(
        start, "stage_running_execution", transition
    )

    db = Mock()
    db.scalar.return_value = ownership
    db.scalars.return_value.all.return_value = reservations

    return db, authorize, transition

def invoke(db, execution):
    return start.stage_protected_running_execution(
        db,
        project_id=execution.project_id,
        execution_id=execution.id,
        actor_user_id=uuid4(),
        started_at=datetime.now(timezone.utc),
    )


def test_protected_start_validates_and_locks_before_transition(monkeypatch):
    execution, ownership, reservations = fixture()
    db, authorize, transition = setup_mocks(
        monkeypatch, execution, ownership, reservations
    )

    result = invoke(db, execution)

    assert result is execution
    authorize.assert_called_once()
    transition.assert_called_once()

    assert db.scalar.call_count == 1
    assert db.scalars.call_count == 1

    for statement in (
        db.scalar.call_args.args[0],
        db.scalars.call_args.args[0],
    ):
        assert statement._for_update_arg is not None

    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.add.assert_not_called()


@pytest.mark.parametrize(
    "mismatch",
    ["execution", "project", "rule"],
)
def test_mismatched_workload_identity_rejected(monkeypatch, mismatch):
    execution, ownership, reservations = fixture()

    if mismatch == "execution":
        ownership.execution_id = uuid4()
    elif mismatch == "project":
        ownership.project_id = uuid4()
    else:
        ownership.rule_id = uuid4()

    db, _, transition = setup_mocks(
        monkeypatch, execution, ownership, reservations
    )

    with pytest.raises(ValueError):
        invoke(db, execution)

    transition.assert_not_called()
    db.commit.assert_not_called()


def test_missing_ownership_prevents_start(monkeypatch):
    execution, _, reservations = fixture()
    db, _, transition = setup_mocks(
        monkeypatch, execution, None, reservations
    )

    with pytest.raises(ValueError):
        invoke(db, execution)

    transition.assert_not_called()
    db.commit.assert_not_called()


def test_missing_source_reservation_prevents_start(monkeypatch):
    execution, ownership, reservations = fixture()
    db, _, transition = setup_mocks(
        monkeypatch, execution, ownership, reservations[:1]
    )

    with pytest.raises(ValueError):
        invoke(db, execution)

    transition.assert_not_called()
    db.commit.assert_not_called()


def test_released_ownership_prevents_start(monkeypatch):
    execution, ownership, reservations = fixture()
    ownership.ownership_state = "released"

    db, _, transition = setup_mocks(
        monkeypatch, execution, ownership, reservations
    )

    with pytest.raises(ValueError):
        invoke(db, execution)

    transition.assert_not_called()
    db.commit.assert_not_called()


def test_authorization_failure_prevents_protection_queries(monkeypatch):
    execution, ownership, reservations = fixture()
    db, authorize, transition = setup_mocks(
        monkeypatch, execution, ownership, reservations
    )
    authorize.side_effect = PermissionError("Access denied")

    with pytest.raises(PermissionError, match="Access denied"):
        invoke(db, execution)

    assert db.mock_calls == []
    transition.assert_not_called()

def test_protected_start_reservation_query_orders_by_id():
    """Document the current locked reservation query ordering."""
    from sqlalchemy.dialects import postgresql

    execution, ownership, reservations = fixture()
    db = Mock()
    db.scalar.return_value = ownership
    db.scalars.return_value.all.return_value = reservations

    installation = SimpleNamespace(id=reservations[0].capacity_control_id)
    source = SimpleNamespace(id=reservations[1].capacity_control_id)

    start._validate_locked_protected_workload(
        db,
        execution=execution,
        project_id=execution.project_id,
        execution_id=execution.id,
        expected_source_id=ownership.data_source_id,
        installation_control=installation,
        source_control=source,
    )

    statement = db.scalars.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert statement._for_update_arg is not None
    assert "ORDER BY" in sql
    assert "data_quality_execution_capacity_reservations.id" in sql
    assert "reservation_scope" not in sql.split("ORDER BY", 1)[1]

    db.commit.assert_not_called()
    db.rollback.assert_not_called()
