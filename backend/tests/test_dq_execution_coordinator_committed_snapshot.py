"""Internal Phase 5E committed-protection verification tests.

No source measurement, API, production database, or capacity release.
"""

from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from app.services.data_quality_execution_coordinator_committed_snapshot import (
    verify_committed_protection,
)


def make_context():
    project_id = uuid4()
    execution_id = uuid4()
    rule_id = uuid4()

    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        status="pending",
    )

    session = Mock()
    factory = Mock(return_value=session)

    return execution, session, factory


def test_pending_protection_verified_in_fresh_session():
    execution, session, factory = make_context()

    with patch(
        "app.services."
        "data_quality_execution_coordinator_committed_snapshot."
        "inspect_protected_execution_snapshot",
        return_value=execution,
    ) as inspect:
        result = verify_committed_protection(
            session_factory=factory,
            project_id=execution.project_id,
            execution_id=execution.id,
            expected_status="pending",
        )

    assert result == execution.id
    factory.assert_called_once_with()
    inspect.assert_called_once_with(
        session,
        project_id=execution.project_id,
        execution_id=execution.id,
        expected_status="pending",
    )
    session.close.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_running_protection_verified_in_fresh_session():
    execution, session, factory = make_context()
    execution.status = "running"

    with patch(
        "app.services."
        "data_quality_execution_coordinator_committed_snapshot."
        "inspect_protected_execution_snapshot",
        return_value=execution,
    ):
        result = verify_committed_protection(
            session_factory=factory,
            project_id=execution.project_id,
            execution_id=execution.id,
            expected_status="running",
        )

    assert result == execution.id
    session.close.assert_called_once_with()


def test_snapshot_failure_closes_session_and_propagates():
    execution, session, factory = make_context()

    with patch(
        "app.services."
        "data_quality_execution_coordinator_committed_snapshot."
        "inspect_protected_execution_snapshot",
        side_effect=ValueError("Protection missing"),
    ):
        with pytest.raises(ValueError, match="Protection missing"):
            verify_committed_protection(
                session_factory=factory,
                project_id=execution.project_id,
                execution_id=execution.id,
                expected_status="pending",
            )

    session.close.assert_called_once_with()
    session.commit.assert_not_called()


def test_session_creation_failure_prevents_verification():
    execution, _, _ = make_context()
    factory = Mock(side_effect=ConnectionError("Unavailable"))

    with patch(
        "app.services."
        "data_quality_execution_coordinator_committed_snapshot."
        "inspect_protected_execution_snapshot",
    ) as inspect:
        with pytest.raises(ConnectionError, match="Unavailable"):
            verify_committed_protection(
                session_factory=factory,
                project_id=execution.project_id,
                execution_id=execution.id,
                expected_status="pending",
            )

    inspect.assert_not_called()


def test_mismatched_execution_identity_rejected():
    execution, session, factory = make_context()

    with patch(
        "app.services."
        "data_quality_execution_coordinator_committed_snapshot."
        "inspect_protected_execution_snapshot",
        return_value=SimpleNamespace(
            id=uuid4(),
            project_id=execution.project_id,
            status="pending",
        ),
    ):
        with pytest.raises(ValueError):
            verify_committed_protection(
                session_factory=factory,
                project_id=execution.project_id,
                execution_id=execution.id,
                expected_status="pending",
            )

    session.close.assert_called_once_with()


@pytest.mark.parametrize(
    "invalid",
    [None, "", 1, True],
)
def test_invalid_session_factory_rejected(invalid):
    execution, _, _ = make_context()

    with pytest.raises(ValueError):
        verify_committed_protection(
            session_factory=invalid,
            project_id=execution.project_id,
            execution_id=execution.id,
            expected_status="pending",
        )


def test_invalid_project_identity_rejected_without_session():
    execution, _, factory = make_context()

    with pytest.raises(ValueError):
        verify_committed_protection(
            session_factory=factory,
            project_id="incorrect",
            execution_id=execution.id,
            expected_status="pending",
        )

    factory.assert_not_called()


def test_invalid_execution_identity_rejected_without_session():
    execution, _, factory = make_context()

    with pytest.raises(ValueError):
        verify_committed_protection(
            session_factory=factory,
            project_id=execution.project_id,
            execution_id="incorrect",
            expected_status="pending",
        )

    factory.assert_not_called()
