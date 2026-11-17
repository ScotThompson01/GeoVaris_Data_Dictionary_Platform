"""Offline tests for internal connection-authorized protected start."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, call
from uuid import uuid4

import pytest

from app.services import data_quality_execution_protected_start as start
from app.services.data_quality_execution_transaction_authorization import (
    TransactionConnectionAuthorizationUnavailableError,
)


def test_connection_authorization_failure_prevents_running(monkeypatch):
    project_id = uuid4()
    execution_id = uuid4()
    data_source_id = uuid4()
    actor_user_id = uuid4()
    started_at = datetime.now(timezone.utc)

    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
        rule_id=uuid4(),
    )

    installation = SimpleNamespace(id=uuid4())
    source = SimpleNamespace(id=uuid4())

    db = Mock()

    authorize_actor = Mock(return_value=(execution, data_source_id, installation, source))
    validate_workload = Mock()
    reject_connection = Mock(
        side_effect=TransactionConnectionAuthorizationUnavailableError(
            "Persisted connection authorization is unavailable."
        )
    )
    stage_running = Mock()

    monkeypatch.setattr(
        start,
        "_lock_authorized_protected_start",
        authorize_actor,
    )
    monkeypatch.setattr(
        start,
        "_validate_locked_protected_workload",
        validate_workload,
    )
    monkeypatch.setattr(
        start,
        "validate_locked_execution_connection_authorization",
        reject_connection,
    )
    monkeypatch.setattr(
        start,
        "stage_running_execution",
        stage_running,
    )

    with pytest.raises(
        TransactionConnectionAuthorizationUnavailableError
    ):
        start.stage_connection_authorized_protected_running_execution(
            db,
            project_id=project_id,
            execution_id=execution_id,
            data_source_id=data_source_id,
            actor_user_id=actor_user_id,
            started_at=started_at,
        )

    authorize_actor.assert_called_once_with(
        db,
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_user_id,
        expected_source_id=data_source_id,
    )
    validate_workload.assert_called_once_with(
        db,
        execution=execution,
        project_id=project_id,
        execution_id=execution_id,
        expected_source_id=data_source_id,
        installation_control=installation,
        source_control=source,
    )
    reject_connection.assert_called_once_with(
        db,
        execution_id=execution_id,
        project_id=project_id,
        data_source_id=data_source_id,
    )

    stage_running.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()

def test_successful_connection_authorization_stages_running_once(monkeypatch):
    project_id = uuid4()
    execution_id = uuid4()
    data_source_id = uuid4()
    actor_user_id = uuid4()
    started_at = datetime.now(timezone.utc)

    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
        rule_id=uuid4(),
    )

    installation = SimpleNamespace(id=uuid4())
    source = SimpleNamespace(id=uuid4())

    db = Mock()
    calls = Mock()
    expected_result = object()

    authorize_actor = Mock(
        return_value=execution,
        side_effect=lambda *args, **kwargs: (
            calls.authorize(),
            (execution, data_source_id, installation, source),
        )[1],
    )
    validate_workload = Mock(
        side_effect=lambda *args, **kwargs: calls.workload(),
    )
    validate_connection = Mock(
        return_value=(data_source_id, 1),
        side_effect=lambda *args, **kwargs: calls.connection(),
    )
    stage_running = Mock(
        return_value=expected_result,
        side_effect=lambda *args, **kwargs: (
            calls.running(),
            expected_result,
        )[1],
    )

    monkeypatch.setattr(
        start,
        "_lock_authorized_protected_start",
        authorize_actor,
    )
    monkeypatch.setattr(
        start,
        "_validate_locked_protected_workload",
        validate_workload,
    )
    monkeypatch.setattr(
        start,
        "validate_locked_execution_connection_authorization",
        validate_connection,
    )
    monkeypatch.setattr(
        start,
        "stage_running_execution",
        stage_running,
    )

    result = start.stage_connection_authorized_protected_running_execution(
        db,
        project_id=project_id,
        execution_id=execution_id,
        data_source_id=data_source_id,
        actor_user_id=actor_user_id,
        started_at=started_at,
    )

    assert result is expected_result

    assert calls.mock_calls == [
        call.authorize(),
        call.workload(),
        call.connection(),
        call.running(),
    ]

    authorize_actor.assert_called_once_with(
        db,
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_user_id,
        expected_source_id=data_source_id,
    )
    validate_workload.assert_called_once_with(
        db,
        execution=execution,
        project_id=project_id,
        execution_id=execution_id,
        expected_source_id=data_source_id,
        installation_control=installation,
        source_control=source,
    )
    validate_connection.assert_called_once_with(
        db,
        execution_id=execution_id,
        project_id=project_id,
        data_source_id=data_source_id,
    )
    stage_running.assert_called_once_with(
        db,
        execution=execution,
        started_at=started_at,
    )

    db.commit.assert_not_called()
    db.rollback.assert_not_called()

def test_actor_authorization_failure_stops_before_protection_checks(monkeypatch):
    project_id = uuid4()
    execution_id = uuid4()
    data_source_id = uuid4()
    actor_user_id = uuid4()
    started_at = datetime.now(timezone.utc)

    installation = SimpleNamespace(id=uuid4())
    source = SimpleNamespace(id=uuid4())

    db = Mock()

    reject_actor = Mock(
        side_effect=ValueError("Actor is not authorized.")
    )
    validate_workload = Mock()
    validate_connection = Mock()
    stage_running = Mock()

    monkeypatch.setattr(
        start,
        "_lock_authorized_protected_start",
        reject_actor,
    )
    monkeypatch.setattr(
        start,
        "_validate_locked_protected_workload",
        validate_workload,
    )
    monkeypatch.setattr(
        start,
        "validate_locked_execution_connection_authorization",
        validate_connection,
    )
    monkeypatch.setattr(
        start,
        "stage_running_execution",
        stage_running,
    )

    with pytest.raises(ValueError, match="Actor is not authorized"):
        start.stage_connection_authorized_protected_running_execution(
            db,
            project_id=project_id,
            execution_id=execution_id,
            data_source_id=data_source_id,
            actor_user_id=actor_user_id,
            started_at=started_at,
        )

    reject_actor.assert_called_once_with(
        db,
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_user_id,
        expected_source_id=data_source_id,
    )

    validate_workload.assert_not_called()
    validate_connection.assert_not_called()
    stage_running.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()

def test_workload_protection_failure_prevents_connection_authorization(monkeypatch):
    project_id = uuid4()
    execution_id = uuid4()
    data_source_id = uuid4()
    actor_user_id = uuid4()
    started_at = datetime.now(timezone.utc)

    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
        rule_id=uuid4(),
    )

    installation = SimpleNamespace(id=uuid4())
    source = SimpleNamespace(id=uuid4())

    db = Mock()

    authorize_actor = Mock(return_value=(execution, data_source_id, installation, source))
    reject_workload = Mock(
        side_effect=ValueError(
            "Protected execution requires two active reservations."
        )
    )
    validate_connection = Mock()
    stage_running = Mock()

    monkeypatch.setattr(
        start,
        "_lock_authorized_protected_start",
        authorize_actor,
    )
    monkeypatch.setattr(
        start,
        "_validate_locked_protected_workload",
        reject_workload,
    )
    monkeypatch.setattr(
        start,
        "validate_locked_execution_connection_authorization",
        validate_connection,
    )
    monkeypatch.setattr(
        start,
        "stage_running_execution",
        stage_running,
    )

    with pytest.raises(
        ValueError,
        match="Protected execution requires two active reservations",
    ):
        start.stage_connection_authorized_protected_running_execution(
            db,
            project_id=project_id,
            execution_id=execution_id,
            data_source_id=data_source_id,
            actor_user_id=actor_user_id,
            started_at=started_at,
        )

    authorize_actor.assert_called_once_with(
        db,
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_user_id,
        expected_source_id=data_source_id,
    )

    reject_workload.assert_called_once_with(
        db,
        execution=execution,
        project_id=project_id,
        execution_id=execution_id,
        expected_source_id=data_source_id,
        installation_control=installation,
        source_control=source,
    )

    validate_connection.assert_not_called()
    stage_running.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()
