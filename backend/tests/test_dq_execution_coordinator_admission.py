"""Test-only contract for internal Phase 5E admission coordination.

No runtime admission activation, API routes, source I/O, or release.
"""

from unittest.mock import Mock, call, patch
from uuid import uuid4

import pytest

from app.services.data_quality_execution_coordinator_admission import (
    commit_and_verify_protected_admission,
)


MODULE = (
    "app.services."
    "data_quality_execution_coordinator_admission"
)


def make_context():
    return {
        "project_id": uuid4(),
        "execution_id": uuid4(),
        "session_factory": Mock(),
        "stage_admission": Mock(),
    }


def test_admission_commits_then_verifies_pending_protection():
    context = make_context()
    events = []

    def transaction(**kwargs):
        events.append("commit")
        assert kwargs["session_factory"] is context["session_factory"]
        assert kwargs["stage"] is context["stage_admission"]
        return context["execution_id"]

    def verification(**kwargs):
        events.append("verify")
        assert kwargs["session_factory"] is context["session_factory"]
        assert kwargs["project_id"] == context["project_id"]
        assert kwargs["execution_id"] == context["execution_id"]
        assert kwargs["expected_status"] == "pending"
        return context["execution_id"]

    with (
        patch(
            MODULE + ".run_coordinator_transaction",
            side_effect=transaction,
        ),
        patch(
            MODULE + ".verify_committed_protection",
            side_effect=verification,
        ),
    ):
        result = commit_and_verify_protected_admission(
            session_factory=context["session_factory"],
            project_id=context["project_id"],
            stage_admission=context["stage_admission"],
        )

    assert result == context["execution_id"]
    assert events == ["commit", "verify"]


def test_stage_or_commit_failure_prevents_verification():
    context = make_context()

    with (
        patch(
            MODULE + ".run_coordinator_transaction",
            side_effect=ConnectionError("Commit outcome unknown"),
        ) as transaction,
        patch(MODULE + ".verify_committed_protection") as verify,
    ):
        with pytest.raises(ConnectionError, match="unknown"):
            commit_and_verify_protected_admission(
                session_factory=context["session_factory"],
                project_id=context["project_id"],
                stage_admission=context["stage_admission"],
            )

    transaction.assert_called_once()
    verify.assert_not_called()


def test_verification_failure_propagates_without_retry():
    context = make_context()

    with (
        patch(
            MODULE + ".run_coordinator_transaction",
            return_value=context["execution_id"],
        ) as transaction,
        patch(
            MODULE + ".verify_committed_protection",
            side_effect=ValueError("Protection missing"),
        ) as verify,
    ):
        with pytest.raises(ValueError, match="Protection missing"):
            commit_and_verify_protected_admission(
                session_factory=context["session_factory"],
                project_id=context["project_id"],
                stage_admission=context["stage_admission"],
            )

    transaction.assert_called_once()
    verify.assert_called_once()


@pytest.mark.parametrize(
    "invalid_result",
    [None, "", 123, True, "00000000-0000-0000-0000-000000000001"],
)
def test_admission_must_return_uuid(invalid_result):
    context = make_context()

    with (
        patch(
            MODULE + ".run_coordinator_transaction",
            return_value=invalid_result,
        ),
        patch(MODULE + ".verify_committed_protection") as verify,
    ):
        with pytest.raises(ValueError):
            commit_and_verify_protected_admission(
                session_factory=context["session_factory"],
                project_id=context["project_id"],
                stage_admission=context["stage_admission"],
            )

    verify.assert_not_called()


def test_mismatched_verification_identity_rejected():
    context = make_context()

    with (
        patch(
            MODULE + ".run_coordinator_transaction",
            return_value=context["execution_id"],
        ),
        patch(
            MODULE + ".verify_committed_protection",
            return_value=uuid4(),
        ),
    ):
        with pytest.raises(ValueError, match="identity"):
            commit_and_verify_protected_admission(
                session_factory=context["session_factory"],
                project_id=context["project_id"],
                stage_admission=context["stage_admission"],
            )


def test_invalid_project_rejected_before_transaction():
    context = make_context()

    with patch(MODULE + ".run_coordinator_transaction") as transaction:
        with pytest.raises(ValueError):
            commit_and_verify_protected_admission(
                session_factory=context["session_factory"],
                project_id="incorrect",
                stage_admission=context["stage_admission"],
            )

    transaction.assert_not_called()


def test_invalid_callback_rejected_before_transaction():
    context = make_context()

    with patch(MODULE + ".run_coordinator_transaction") as transaction:
        with pytest.raises(ValueError):
            commit_and_verify_protected_admission(
                session_factory=context["session_factory"],
                project_id=context["project_id"],
                stage_admission=None,
            )

    transaction.assert_not_called()


def test_invalid_factory_rejected_before_transaction():
    context = make_context()

    with patch(MODULE + ".run_coordinator_transaction") as transaction:
        with pytest.raises(ValueError):
            commit_and_verify_protected_admission(
                session_factory=None,
                project_id=context["project_id"],
                stage_admission=context["stage_admission"],
            )

    transaction.assert_not_called()
