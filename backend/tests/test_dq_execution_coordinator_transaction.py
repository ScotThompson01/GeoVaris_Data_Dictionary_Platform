"""Internal Phase 5E transaction boundary tests.

No production database, API, worker, or client-source access.
"""

from unittest.mock import Mock

import pytest

from app.services.data_quality_execution_coordinator_transaction import (
    run_coordinator_transaction,
)


def make_factory():
    sessions = []

    def factory():
        session = Mock()
        sessions.append(session)
        return session

    return factory, sessions


def test_successful_stage_commits_once_and_closes():
    factory, sessions = make_factory()
    stage = Mock(return_value="execution-id")

    result = run_coordinator_transaction(
        session_factory=factory,
        stage=stage,
    )

    assert result == "execution-id"
    assert len(sessions) == 1
    stage.assert_called_once_with(sessions[0])
    sessions[0].commit.assert_called_once_with()
    sessions[0].rollback.assert_not_called()
    sessions[0].close.assert_called_once_with()


def test_stage_failure_rolls_back_without_commit():
    factory, sessions = make_factory()
    stage = Mock(side_effect=ValueError("Rejected"))

    with pytest.raises(ValueError, match="Rejected"):
        run_coordinator_transaction(
            session_factory=factory,
            stage=stage,
        )

    assert len(sessions) == 1
    sessions[0].commit.assert_not_called()
    sessions[0].rollback.assert_called_once_with()
    sessions[0].close.assert_called_once_with()


def test_commit_exception_propagates_without_claiming_success():
    factory, sessions = make_factory()
    sessions_before = sessions
    stage = Mock(return_value="staged")

    def failing_factory():
        session = Mock()
        session.commit.side_effect = ConnectionError(
            "Commit outcome unknown"
        )
        sessions_before.append(session)
        return session

    with pytest.raises(ConnectionError, match="unknown"):
        run_coordinator_transaction(
            session_factory=failing_factory,
            stage=stage,
        )

    assert len(sessions) == 1
    sessions[0].commit.assert_called_once_with()
    sessions[0].rollback.assert_called_once_with()
    sessions[0].close.assert_called_once_with()


def test_stage_is_not_called_if_session_creation_fails():
    stage = Mock()

    def failing_factory():
        raise ConnectionError("Database unavailable")

    with pytest.raises(ConnectionError, match="unavailable"):
        run_coordinator_transaction(
            session_factory=failing_factory,
            stage=stage,
        )

    stage.assert_not_called()


def test_invalid_stage_or_factory_rejected():
    with pytest.raises(ValueError):
        run_coordinator_transaction(
            session_factory=None,
            stage=lambda db: None,
        )

    with pytest.raises(ValueError):
        run_coordinator_transaction(
            session_factory=lambda: Mock(),
            stage=None,
        )


def test_new_invocation_uses_new_session():
    factory, sessions = make_factory()

    first = run_coordinator_transaction(
        session_factory=factory,
        stage=lambda db: "first",
    )
    second = run_coordinator_transaction(
        session_factory=factory,
        stage=lambda db: "second",
    )

    assert (first, second) == ("first", "second")
    assert len(sessions) == 2
    assert sessions[0] is not sessions[1]

    for session in sessions:
        session.commit.assert_called_once_with()
        session.close.assert_called_once_with()


def test_close_failure_does_not_mask_uncertain_commit():
    """A failed close must not obscure an unknown commit outcome."""
    session = Mock()
    original_error = ConnectionError("Commit outcome unknown")

    session.commit.side_effect = original_error
    session.close.side_effect = RuntimeError("Session close failed")

    stage = Mock(return_value="staged")

    with pytest.raises(ConnectionError) as captured:
        run_coordinator_transaction(
            session_factory=Mock(return_value=session),
            stage=stage,
        )

    assert captured.value is original_error
    stage.assert_called_once_with(session)
    session.commit.assert_called_once_with()
    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()


def test_close_failure_does_not_mask_staging_error():
    """A failed close must not obscure why staging was rejected."""
    session = Mock()
    original_error = ValueError("Admission staging rejected")

    session.close.side_effect = RuntimeError("Session close failed")
    stage = Mock(side_effect=original_error)

    with pytest.raises(ValueError) as captured:
        run_coordinator_transaction(
            session_factory=Mock(return_value=session),
            stage=stage,
        )

    assert captured.value is original_error
    stage.assert_called_once_with(session)
    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()
