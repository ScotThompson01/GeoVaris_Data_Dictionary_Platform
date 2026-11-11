"""Offline tests for standalone connection authorization coordination.

Only synthetic identities and fake sessions are used. The real transaction
helper is exercised; staging and independent verification are mocked.
No PostgreSQL connection, worker, runtime admission, or measurement occurs.
"""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.services import (
    data_quality_execution_connection_authorization_coordinator as coordinator,
)
from app.services.postgresql_execution_authorization import (
    PostgreSQLExecutionConnectionSnapshot,
)


def make_context(monkeypatch):
    execution_id = uuid4()
    project_id = uuid4()
    data_source_id = uuid4()

    snapshot = PostgreSQLExecutionConnectionSnapshot(
        config=SimpleNamespace(
            host="synthetic.example.invalid",
            port=5432,
            database="synthetic_test",
            username="synthetic_user",
            ssl_mode="verify-full",
            host_address="192.0.2.10",
        ),
        connection_revision=3,
    )

    evidence = SimpleNamespace(
        execution_id=execution_id,
        project_id=project_id,
        data_source_id=data_source_id,
        connection_revision=3,
    )

    session = Mock()
    session_factory = Mock(return_value=session)

    staging = Mock(return_value=evidence)
    verification = Mock(return_value=execution_id)

    monkeypatch.setattr(
        coordinator,
        "stage_execution_connection_authorization",
        staging,
    )
    monkeypatch.setattr(
        coordinator,
        "verify_committed_connection_authorization",
        verification,
    )

    arguments = {
        "session_factory": session_factory,
        "execution_id": execution_id,
        "project_id": project_id,
        "data_source_id": data_source_id,
        "snapshot": snapshot,
    }

    return SimpleNamespace(
        args=arguments,
        evidence=evidence,
        session=session,
        factory=session_factory,
        staging=staging,
        verification=verification,
    )


def test_successful_authorization_commits_before_verification(monkeypatch):
    context = make_context(monkeypatch)

    def verify_after_commit(**kwargs):
        context.session.commit.assert_called_once_with()
        context.session.close.assert_called_once_with()
        context.session.rollback.assert_not_called()
        return context.args["execution_id"]

    context.verification.side_effect = verify_after_commit

    result = coordinator.commit_and_verify_connection_authorization(
        **context.args
    )

    assert result == context.args["execution_id"]
    context.factory.assert_called_once_with()
    context.staging.assert_called_once_with(
        context.session,
        execution_id=context.args["execution_id"],
        project_id=context.args["project_id"],
        data_source_id=context.args["data_source_id"],
        snapshot=context.args["snapshot"],
    )
    context.session.commit.assert_called_once_with()
    context.session.close.assert_called_once_with()
    context.verification.assert_called_once_with(
        session_factory=context.factory,
        execution_id=context.args["execution_id"],
        project_id=context.args["project_id"],
        data_source_id=context.args["data_source_id"],
        expected_connection_revision=3,
    )


@pytest.mark.parametrize(
    "field",
    ["execution_id", "project_id", "data_source_id"],
)
def test_mismatched_staged_identity_blocks_commit(monkeypatch, field):
    context = make_context(monkeypatch)
    setattr(context.evidence, field, uuid4())

    with pytest.raises(ValueError, match="does not match"):
        coordinator.commit_and_verify_connection_authorization(
            **context.args
        )

    context.session.commit.assert_not_called()
    context.session.rollback.assert_called_once_with()
    context.session.close.assert_called_once_with()
    context.verification.assert_not_called()


@pytest.mark.parametrize(
    "revision",
    [0, -1, True, 3.0, "3", None, 4],
)
def test_invalid_or_mismatched_staged_revision_blocks_commit(
    monkeypatch, revision
):
    context = make_context(monkeypatch)
    context.evidence.connection_revision = revision

    with pytest.raises(ValueError, match="does not match"):
        coordinator.commit_and_verify_connection_authorization(
            **context.args
        )

    context.session.commit.assert_not_called()
    context.session.rollback.assert_called_once_with()
    context.verification.assert_not_called()


def test_missing_staged_evidence_blocks_commit(monkeypatch):
    context = make_context(monkeypatch)
    context.staging.return_value = None

    with pytest.raises(ValueError, match="does not match"):
        coordinator.commit_and_verify_connection_authorization(
            **context.args
        )

    context.session.commit.assert_not_called()
    context.session.rollback.assert_called_once_with()
    context.verification.assert_not_called()


def test_staging_failure_rolls_back_and_skips_verification(monkeypatch):
    context = make_context(monkeypatch)
    context.staging.side_effect = RuntimeError("synthetic staging rejection")

    with pytest.raises(RuntimeError, match="synthetic staging rejection"):
        coordinator.commit_and_verify_connection_authorization(
            **context.args
        )

    context.factory.assert_called_once_with()
    context.session.commit.assert_not_called()
    context.session.rollback.assert_called_once_with()
    context.session.close.assert_called_once_with()
    context.verification.assert_not_called()


def test_commit_exception_propagates_without_verification_or_retry(
    monkeypatch,
):
    context = make_context(monkeypatch)
    context.session.commit.side_effect = ConnectionError(
        "synthetic uncertain commit"
    )

    with pytest.raises(ConnectionError, match="uncertain commit"):
        coordinator.commit_and_verify_connection_authorization(
            **context.args
        )

    context.factory.assert_called_once_with()
    context.staging.assert_called_once()
    context.session.commit.assert_called_once_with()
    context.session.rollback.assert_called_once_with()
    context.session.close.assert_called_once_with()
    context.verification.assert_not_called()


def test_verification_failure_propagates_without_new_commit(monkeypatch):
    context = make_context(monkeypatch)
    context.verification.side_effect = ValueError(
        "synthetic missing committed evidence"
    )

    with pytest.raises(ValueError, match="missing committed evidence"):
        coordinator.commit_and_verify_connection_authorization(
            **context.args
        )

    context.factory.assert_called_once_with()
    context.session.commit.assert_called_once_with()
    context.session.rollback.assert_not_called()
    context.session.close.assert_called_once_with()
    context.verification.assert_called_once()


@pytest.mark.parametrize(
    "verified_id",
    [None, "not-a-uuid", 123],
)
def test_invalid_verified_identity_rejected(monkeypatch, verified_id):
    context = make_context(monkeypatch)
    context.verification.return_value = verified_id

    with pytest.raises(ValueError, match="execution identity mismatch"):
        coordinator.commit_and_verify_connection_authorization(
            **context.args
        )

    context.session.commit.assert_called_once_with()
    context.verification.assert_called_once()


def test_mismatched_verified_uuid_rejected(monkeypatch):
    context = make_context(monkeypatch)
    context.verification.return_value = uuid4()

    with pytest.raises(ValueError, match="execution identity mismatch"):
        coordinator.commit_and_verify_connection_authorization(
            **context.args
        )

    context.session.commit.assert_called_once_with()
    context.verification.assert_called_once()


@pytest.mark.parametrize(
    "field",
    ["execution_id", "project_id", "data_source_id"],
)
@pytest.mark.parametrize(
    "invalid",
    [None, "invalid", 1],
)
def test_invalid_input_identity_rejected_before_session(
    monkeypatch, field, invalid
):
    context = make_context(monkeypatch)
    context.args[field] = invalid

    with pytest.raises(ValueError, match="UUID identities"):
        coordinator.commit_and_verify_connection_authorization(
            **context.args
        )

    context.factory.assert_not_called()
    context.staging.assert_not_called()
    context.verification.assert_not_called()


@pytest.mark.parametrize("invalid_factory", [None, False, "factory", 42])
def test_invalid_session_factory_rejected(monkeypatch, invalid_factory):
    context = make_context(monkeypatch)
    context.args["session_factory"] = invalid_factory

    with pytest.raises(ValueError, match="session factory"):
        coordinator.commit_and_verify_connection_authorization(
            **context.args
        )

    context.factory.assert_not_called()
    context.staging.assert_not_called()
    context.verification.assert_not_called()


@pytest.mark.parametrize(
    "invalid_snapshot",
    [None, "snapshot", SimpleNamespace(connection_revision=3)],
)
def test_invalid_snapshot_rejected_before_session(
    monkeypatch, invalid_snapshot
):
    context = make_context(monkeypatch)
    context.args["snapshot"] = invalid_snapshot

    with pytest.raises(ValueError, match="PostgreSQL snapshot"):
        coordinator.commit_and_verify_connection_authorization(
            **context.args
        )

    context.factory.assert_not_called()
    context.staging.assert_not_called()
    context.verification.assert_not_called()


@pytest.mark.parametrize("revision", [0, -1, True, 3.0, "3", None])
def test_invalid_snapshot_revision_rejected_before_session(
    monkeypatch, revision
):
    context = make_context(monkeypatch)
    context.args["snapshot"] = PostgreSQLExecutionConnectionSnapshot(
        config=context.args["snapshot"].config,
        connection_revision=revision,
    )

    with pytest.raises(ValueError, match="positive connection revision"):
        coordinator.commit_and_verify_connection_authorization(
            **context.args
        )

    context.factory.assert_not_called()
    context.staging.assert_not_called()
    context.verification.assert_not_called()


def test_session_creation_failure_prevents_staging(monkeypatch):
    context = make_context(monkeypatch)
    context.factory.side_effect = RuntimeError(
        "synthetic session unavailable"
    )

    with pytest.raises(RuntimeError, match="session unavailable"):
        coordinator.commit_and_verify_connection_authorization(
            **context.args
        )

    context.factory.assert_called_once_with()
    context.staging.assert_not_called()
    context.verification.assert_not_called()


def test_close_failure_does_not_claim_success(monkeypatch):
    context = make_context(monkeypatch)
    context.session.close.side_effect = RuntimeError(
        "synthetic close failure"
    )

    with pytest.raises(RuntimeError, match="close failure"):
        coordinator.commit_and_verify_connection_authorization(
            **context.args
        )

    context.session.commit.assert_called_once_with()
    context.session.close.assert_called_once_with()
    context.verification.assert_not_called()


def test_staging_and_verification_are_each_invoked_once(monkeypatch):
    context = make_context(monkeypatch)

    result = coordinator.commit_and_verify_connection_authorization(
        **context.args
    )

    assert result == context.args["execution_id"]
    context.factory.assert_called_once_with()
    context.staging.assert_called_once()
    context.verification.assert_called_once()
    context.session.commit.assert_called_once_with()
    context.session.rollback.assert_not_called()
    context.session.close.assert_called_once_with()
