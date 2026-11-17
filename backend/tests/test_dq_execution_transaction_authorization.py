"""Offline tests for transaction-scoped execution connection authorization.

All session records and PostgreSQL revalidation responses are synthetic.
No database engine, network connection, worker, or source measurement runs.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.models.data_quality_execution_connection_authorization import (
    DataQualityExecutionConnectionAuthorization,
)
from app.models.data_quality_workload_ownership import (
    DataQualityWorkloadOwnership,
)
from app.services import data_quality_execution_transaction_authorization as module


def make_context(monkeypatch):
    execution_id = uuid4()
    project_id = uuid4()
    data_source_id = uuid4()
    timestamp = datetime.now(timezone.utc)

    ownership = SimpleNamespace(
        execution_id=execution_id,
        project_id=project_id,
        data_source_id=data_source_id,
        ownership_state="reserved",
        released_at=None,
        release_actor=None,
        release_reason=None,
        release_evidence_reference=None,
    )

    evidence = SimpleNamespace(
        execution_id=execution_id,
        project_id=project_id,
        data_source_id=data_source_id,
        connection_revision=3,
        authorized_host="approved.example.invalid",
        authorized_port=5432,
        authorized_database="approved_database",
        authorized_ip="192.0.2.10",
        authorized_at=timestamp,
    )

    current = SimpleNamespace(
        data_source_id=data_source_id,
        host=evidence.authorized_host,
        port=evidence.authorized_port,
        database_name=evidence.authorized_database,
        connection_revision=evidence.connection_revision,
        is_verified=True,
        verified_at=timestamp,
    )

    db = Mock()
    db.scalar.side_effect = [ownership, evidence]

    revalidator = Mock(return_value=current)
    monkeypatch.setattr(
        module,
        "revalidate_postgresql_execution_connection",
        revalidator,
    )

    return {
        "db": db,
        "execution_id": execution_id,
        "project_id": project_id,
        "data_source_id": data_source_id,
        "ownership": ownership,
        "evidence": evidence,
        "current": current,
        "revalidator": revalidator,
    }


def invoke(context, **overrides):
    arguments = {
        "db": context["db"],
        "execution_id": context["execution_id"],
        "project_id": context["project_id"],
        "data_source_id": context["data_source_id"],
    }
    arguments.update(overrides)
    return module.validate_locked_execution_connection_authorization(
        **arguments
    )


def assert_no_transaction_or_source_actions(context):
    db = context["db"]
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.flush.assert_not_called()
    db.add.assert_not_called()
    db.delete.assert_not_called()
    db.execute.assert_not_called()
    db.query.assert_not_called()
    db.close.assert_not_called()


def assert_authorization_unavailable(context):
    with pytest.raises(
        module.TransactionConnectionAuthorizationUnavailableError
    ):
        invoke(context)

    assert_no_transaction_or_source_actions(context)


def test_valid_authorization_returns_source_and_revision(monkeypatch):
    context = make_context(monkeypatch)

    result = invoke(context)

    assert result == (context["data_source_id"], 3)
    assert context["db"].scalar.call_count == 2

    context["revalidator"].assert_called_once_with(
        context["db"],
        data_source_id=context["data_source_id"],
        expected_host=context["evidence"].authorized_host,
        expected_port=context["evidence"].authorized_port,
        expected_database=context["evidence"].authorized_database,
        expected_revision=3,
    )

    assert_no_transaction_or_source_actions(context)


def test_both_evidence_reads_request_row_locks(monkeypatch):
    context = make_context(monkeypatch)

    invoke(context)

    calls = context["db"].scalar.call_args_list
    assert len(calls) == 2

    first_statement = calls[0].args[0]
    second_statement = calls[1].args[0]

    assert first_statement.column_descriptions[0]["entity"] is (
        DataQualityWorkloadOwnership
    )
    assert second_statement.column_descriptions[0]["entity"] is (
        DataQualityExecutionConnectionAuthorization
    )

    assert first_statement._for_update_arg is not None
    assert second_statement._for_update_arg is not None
    assert_no_transaction_or_source_actions(context)


@pytest.mark.parametrize("invalid_db", [None])
def test_missing_session_rejected_before_query(monkeypatch, invalid_db):
    context = make_context(monkeypatch)

    with pytest.raises(ValueError, match="database session"):
        invoke(context, db=invalid_db)

    context["db"].scalar.assert_not_called()
    context["revalidator"].assert_not_called()


@pytest.mark.parametrize(
    "identity_name",
    ["execution_id", "project_id", "data_source_id"],
)
@pytest.mark.parametrize(
    "invalid_identity",
    [None, "not-a-uuid", 3, object()],
)
def test_invalid_call_identity_rejected_before_query(
    monkeypatch, identity_name, invalid_identity
):
    context = make_context(monkeypatch)

    with pytest.raises(ValueError, match="UUID"):
        invoke(context, **{identity_name: invalid_identity})

    context["db"].scalar.assert_not_called()
    context["revalidator"].assert_not_called()
    assert_no_transaction_or_source_actions(context)


def test_missing_ownership_fails_closed(monkeypatch):
    context = make_context(monkeypatch)
    context["db"].scalar.side_effect = [None]

    assert_authorization_unavailable(context)

    assert context["db"].scalar.call_count == 1
    context["revalidator"].assert_not_called()


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("execution_id", uuid4()),
        ("project_id", uuid4()),
        ("data_source_id", uuid4()),
        ("data_source_id", None),
        ("ownership_state", "released"),
        ("ownership_state", "RESERVED"),
        ("ownership_state", "unresolved"),
        ("ownership_state", None),
        ("released_at", datetime.now(timezone.utc)),
        ("release_actor", uuid4()),
        ("release_reason", "test"),
        ("release_evidence_reference", "test"),
    ],
)
def test_invalid_ownership_fails_before_authorization_read(
    monkeypatch, field_name, invalid_value
):
    context = make_context(monkeypatch)
    setattr(context["ownership"], field_name, invalid_value)

    assert_authorization_unavailable(context)

    assert context["db"].scalar.call_count == 1
    context["revalidator"].assert_not_called()


def test_missing_authorization_evidence_fails_closed(monkeypatch):
    context = make_context(monkeypatch)
    context["db"].scalar.side_effect = [context["ownership"], None]

    assert_authorization_unavailable(context)

    assert context["db"].scalar.call_count == 2
    context["revalidator"].assert_not_called()


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("execution_id", uuid4()),
        ("project_id", uuid4()),
        ("data_source_id", uuid4()),
        ("connection_revision", None),
        ("connection_revision", True),
        ("connection_revision", "3"),
        ("connection_revision", 0),
        ("connection_revision", -1),
        ("authorized_host", None),
        ("authorized_host", ""),
        ("authorized_host", "   "),
        ("authorized_port", None),
        ("authorized_port", True),
        ("authorized_port", 0),
        ("authorized_port", 65536),
        ("authorized_port", "5432"),
        ("authorized_database", None),
        ("authorized_database", " "),
        ("authorized_ip", None),
        ("authorized_ip", " "),
        ("authorized_ip", "not-an-ip"),
        ("authorized_at", None),
        ("authorized_at", "not-a-datetime"),
        ("authorized_at", datetime(2026, 1, 1)),
    ],
)
def test_invalid_persisted_evidence_fails_before_revalidation(
    monkeypatch, field_name, invalid_value
):
    context = make_context(monkeypatch)
    setattr(context["evidence"], field_name, invalid_value)

    assert_authorization_unavailable(context)

    assert context["db"].scalar.call_count == 2
    context["revalidator"].assert_not_called()


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("data_source_id", uuid4()),
        ("host", "other.example.invalid"),
        ("port", 5433),
        ("database_name", "other_database"),
        ("connection_revision", 4),
        ("is_verified", False),
        ("verified_at", None),
    ],
)
def test_current_identity_mismatch_fails_closed(
    monkeypatch, field_name, invalid_value
):
    context = make_context(monkeypatch)
    setattr(context["current"], field_name, invalid_value)

    assert_authorization_unavailable(context)

    context["revalidator"].assert_called_once()


def test_missing_revalidated_identity_fails_closed(monkeypatch):
    context = make_context(monkeypatch)
    context["revalidator"].return_value = None

    assert_authorization_unavailable(context)

    context["revalidator"].assert_called_once()


def test_revalidation_exception_propagates_without_retry(monkeypatch):
    context = make_context(monkeypatch)
    context["revalidator"].side_effect = ValueError(
        "Synthetic revoked connection"
    )

    with pytest.raises(ValueError, match="Synthetic revoked"):
        invoke(context)

    context["revalidator"].assert_called_once()
    assert context["db"].scalar.call_count == 2
    assert_no_transaction_or_source_actions(context)


def test_database_read_exception_propagates_without_retry(monkeypatch):
    context = make_context(monkeypatch)
    context["db"].scalar.side_effect = RuntimeError(
        "Synthetic database read failure"
    )

    with pytest.raises(RuntimeError, match="Synthetic database"):
        invoke(context)

    assert context["db"].scalar.call_count == 1
    context["revalidator"].assert_not_called()
    assert_no_transaction_or_source_actions(context)


def test_service_has_no_implicit_commit_or_session_factory():
    assert module.validate_locked_execution_connection_authorization
    assert not hasattr(module, "session_factory")
