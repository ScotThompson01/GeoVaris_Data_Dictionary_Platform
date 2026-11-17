"""Offline tests for protected-start authorization and capacity lock order."""

from unittest.mock import Mock, call
from uuid import uuid4

import pytest

from app.services import data_quality_execution_protected_start as start


def setup_helpers(monkeypatch, *, source_id=None):
    source_id = source_id or uuid4()
    events = Mock()
    db = Mock()
    execution = object()
    installation = object()
    source = object()

    def authorize(*args, **kwargs):
        events.authorize()

    def locate(*args, **kwargs):
        events.locate()
        return source_id

    def capacity(*args, **kwargs):
        events.capacity()
        return installation, source

    def lock_execution(*args, **kwargs):
        events.execution()
        return execution

    monkeypatch.setattr(start, "require_dq_rule_executor", authorize)
    monkeypatch.setattr(start, "_locate_protected_execution_source", locate)
    monkeypatch.setattr(
        start, "lock_existing_execution_capacity_controls", capacity
    )
    monkeypatch.setattr(
        start, "lock_existing_project_execution", lock_execution
    )

    return db, events, execution, installation, source, source_id


def test_authorization_and_capacity_precede_execution_lock(monkeypatch):
    db, events, execution, installation, source, source_id = setup_helpers(
        monkeypatch
    )

    result = start._lock_authorized_protected_start(
        db,
        project_id=uuid4(),
        execution_id=uuid4(),
        actor_user_id=uuid4(),
        expected_source_id=source_id,
    )

    assert result == (execution, source_id, installation, source)
    assert events.mock_calls == [
        call.authorize(),
        call.locate(),
        call.capacity(),
        call.execution(),
    ]
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.flush.assert_not_called()


def test_explicit_source_mismatch_prevents_locks(monkeypatch):
    db, events, *_ = setup_helpers(monkeypatch)

    with pytest.raises(ValueError, match="source identity mismatch"):
        start._lock_authorized_protected_start(
            db,
            project_id=uuid4(),
            execution_id=uuid4(),
            actor_user_id=uuid4(),
            expected_source_id=uuid4(),
        )

    assert events.mock_calls == [
        call.authorize(),
        call.locate(),
    ]


@pytest.mark.parametrize(
    "invalid_field",
    ["project_id", "execution_id", "actor_user_id", "expected_source_id"],
)
def test_invalid_identity_prevents_authorization(monkeypatch, invalid_field):
    db, events, *_ = setup_helpers(monkeypatch)

    arguments = {
        "project_id": uuid4(),
        "execution_id": uuid4(),
        "actor_user_id": uuid4(),
        "expected_source_id": uuid4(),
    }
    arguments[invalid_field] = "invalid"

    with pytest.raises(ValueError, match="Invalid"):
        start._lock_authorized_protected_start(db, **arguments)

    assert events.mock_calls == []


def test_authorization_failure_prevents_all_locks(monkeypatch):
    db, events, *_ = setup_helpers(monkeypatch)

    def reject(*args, **kwargs):
        events.authorize()
        raise PermissionError("Access denied.")

    monkeypatch.setattr(start, "require_dq_rule_executor", reject)

    with pytest.raises(PermissionError, match="Access denied"):
        start._lock_authorized_protected_start(
            db,
            project_id=uuid4(),
            execution_id=uuid4(),
            actor_user_id=uuid4(),
        )

    assert events.mock_calls == [call.authorize()]


def test_capacity_failure_prevents_execution_lock(monkeypatch):
    db, events, *_ = setup_helpers(monkeypatch)

    def reject_capacity(*args, **kwargs):
        events.capacity()
        raise ValueError("Capacity control unavailable.")

    monkeypatch.setattr(
        start, "lock_existing_execution_capacity_controls", reject_capacity
    )

    with pytest.raises(ValueError, match="Capacity control unavailable"):
        start._lock_authorized_protected_start(
            db,
            project_id=uuid4(),
            execution_id=uuid4(),
            actor_user_id=uuid4(),
        )

    assert events.mock_calls == [
        call.authorize(),
        call.locate(),
        call.capacity(),
    ]
