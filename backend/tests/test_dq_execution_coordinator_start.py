"""Internal Phase 5E protected-start coordinator contract tests.

No runtime activation, source measurement, or capacity release.
"""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from app.services.data_quality_execution_coordinator_start import (
    commit_and_verify_protected_start,
)


MODULE = "app.services.data_quality_execution_coordinator_start"


def make_context():
    return {
        "project_id": uuid4(),
        "execution_id": uuid4(),
        "session_factory": Mock(),
        "stage_start": Mock(),
    }


def test_pending_verified_before_running_commit_and_verification():
    context = make_context()
    events = []

    def verify(**kwargs):
        events.append("verify_" + kwargs["expected_status"])
        assert kwargs["session_factory"] is context["session_factory"]
        assert kwargs["project_id"] == context["project_id"]
        assert kwargs["execution_id"] == context["execution_id"]
        return context["execution_id"]

    def transaction(**kwargs):
        events.append("commit_running")
        assert kwargs["session_factory"] is context["session_factory"]
        assert kwargs["stage"] is context["stage_start"]
        return context["execution_id"]

    with (
        patch(
            MODULE + ".verify_committed_protection",
            side_effect=verify,
        ),
        patch(
            MODULE + ".run_coordinator_transaction",
            side_effect=transaction,
        ),
    ):
        result = commit_and_verify_protected_start(
            session_factory=context["session_factory"],
            project_id=context["project_id"],
            execution_id=context["execution_id"],
            stage_start=context["stage_start"],
        )

    assert result == context["execution_id"]
    assert events == [
        "verify_pending",
        "commit_running",
        "verify_running",
    ]


def test_missing_pending_protection_prevents_start():
    context = make_context()

    with (
        patch(
            MODULE + ".verify_committed_protection",
            side_effect=ValueError("Missing protection"),
        ),
        patch(MODULE + ".run_coordinator_transaction") as transaction,
    ):
        with pytest.raises(ValueError, match="Missing protection"):
            commit_and_verify_protected_start(
                session_factory=context["session_factory"],
                project_id=context["project_id"],
                execution_id=context["execution_id"],
                stage_start=context["stage_start"],
            )

    transaction.assert_not_called()


def test_running_commit_failure_prevents_running_verification():
    context = make_context()
    statuses = []

    def verify(**kwargs):
        statuses.append(kwargs["expected_status"])
        return context["execution_id"]

    with (
        patch(
            MODULE + ".verify_committed_protection",
            side_effect=verify,
        ),
        patch(
            MODULE + ".run_coordinator_transaction",
            side_effect=ConnectionError("Commit outcome unknown"),
        ),
    ):
        with pytest.raises(ConnectionError, match="unknown"):
            commit_and_verify_protected_start(
                session_factory=context["session_factory"],
                project_id=context["project_id"],
                execution_id=context["execution_id"],
                stage_start=context["stage_start"],
            )

    assert statuses == ["pending"]


def test_running_verification_failure_propagates_without_retry():
    context = make_context()

    def verify(**kwargs):
        if kwargs["expected_status"] == "running":
            raise ValueError("RUNNING protection missing")
        return context["execution_id"]

    with (
        patch(
            MODULE + ".verify_committed_protection",
            side_effect=verify,
        ),
        patch(
            MODULE + ".run_coordinator_transaction",
            return_value=context["execution_id"],
        ) as transaction,
    ):
        with pytest.raises(ValueError, match="RUNNING protection missing"):
            commit_and_verify_protected_start(
                session_factory=context["session_factory"],
                project_id=context["project_id"],
                execution_id=context["execution_id"],
                stage_start=context["stage_start"],
            )

    transaction.assert_called_once()


def test_start_stage_must_return_matching_execution_uuid():
    context = make_context()

    with (
        patch(
            MODULE + ".verify_committed_protection",
            return_value=context["execution_id"],
        ) as verify,
        patch(
            MODULE + ".run_coordinator_transaction",
            return_value=uuid4(),
        ),
    ):
        with pytest.raises(ValueError, match="identity"):
            commit_and_verify_protected_start(
                session_factory=context["session_factory"],
                project_id=context["project_id"],
                execution_id=context["execution_id"],
                stage_start=context["stage_start"],
            )

    assert verify.call_count == 1


def test_pending_verification_identity_mismatch_blocks_start():
    context = make_context()

    with (
        patch(
            MODULE + ".verify_committed_protection",
            return_value=uuid4(),
        ),
        patch(MODULE + ".run_coordinator_transaction") as transaction,
    ):
        with pytest.raises(ValueError, match="identity"):
            commit_and_verify_protected_start(
                session_factory=context["session_factory"],
                project_id=context["project_id"],
                execution_id=context["execution_id"],
                stage_start=context["stage_start"],
            )

    transaction.assert_not_called()


@pytest.mark.parametrize(
    "invalid",
    [None, "", 123, True],
)
def test_invalid_execution_identity_rejected(invalid):
    context = make_context()

    with patch(MODULE + ".run_coordinator_transaction") as transaction:
        with pytest.raises(ValueError):
            commit_and_verify_protected_start(
                session_factory=context["session_factory"],
                project_id=context["project_id"],
                execution_id=invalid,
                stage_start=context["stage_start"],
            )

    transaction.assert_not_called()


def test_invalid_factory_rejected_before_verification():
    context = make_context()

    with patch(MODULE + ".verify_committed_protection") as verify:
        with pytest.raises(ValueError):
            commit_and_verify_protected_start(
                session_factory=None,
                project_id=context["project_id"],
                execution_id=context["execution_id"],
                stage_start=context["stage_start"],
            )

    verify.assert_not_called()


def test_invalid_stage_callback_rejected_before_verification():
    context = make_context()

    with patch(MODULE + ".verify_committed_protection") as verify:
        with pytest.raises(ValueError):
            commit_and_verify_protected_start(
                session_factory=context["session_factory"],
                project_id=context["project_id"],
                execution_id=context["execution_id"],
                stage_start=None,
            )

    verify.assert_not_called()
