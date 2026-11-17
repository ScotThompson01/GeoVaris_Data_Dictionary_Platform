"""Offline regression tests for protected-start transaction lock ordering."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, call
from uuid import uuid4

from app.services import data_quality_execution_protected_start as start


def test_protected_start_acquires_capacity_before_execution_lock(monkeypatch):
    project_id = uuid4()
    execution_id = uuid4()
    source_id = uuid4()
    actor_id = uuid4()

    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
        rule_id=uuid4(),
        status="pending",
    )

    events = Mock()
    db = Mock()

    def authorize(*args, **kwargs):
        events.authorize()

    def locate_source(*args, **kwargs):
        events.locate_source()
        return source_id

    def lock_capacity(*args, **kwargs):
        events.capacity()
        return object(), object()

    def lock_execution(*args, **kwargs):
        events.execution()
        return execution

    def validate_workload(*args, **kwargs):
        events.workload()

    def stage_running(*args, **kwargs):
        events.running()
        return execution

    monkeypatch.setattr(
        start, "require_dq_rule_executor", authorize, raising=False
    )
    monkeypatch.setattr(
        start, "_locate_protected_execution_source", locate_source,
        raising=False,
    )
    monkeypatch.setattr(
        start, "lock_existing_execution_capacity_controls", lock_capacity,
        raising=False,
    )
    monkeypatch.setattr(
        start, "lock_existing_project_execution", lock_execution,
        raising=False,
    )
    monkeypatch.setattr(
        start, "_validate_locked_protected_workload", validate_workload
    )
    monkeypatch.setattr(
        start, "stage_running_execution", stage_running
    )

    result = start.stage_protected_running_execution(
        db,
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_id,
        started_at=datetime.now(timezone.utc),
    )

    assert result is execution
    assert events.mock_calls == [
        call.authorize(),
        call.locate_source(),
        call.capacity(),
        call.execution(),
        call.workload(),
        call.running(),
    ]

    db.commit.assert_not_called()
    db.rollback.assert_not_called()
