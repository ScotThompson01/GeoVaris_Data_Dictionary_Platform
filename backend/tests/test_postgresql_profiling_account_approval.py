"""Security contract for trusted PostgreSQL profiling account approval."""

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.connectors.database.base import DatabaseConnectionConfig
from app.services import postgresql_profiling_account_approval as service
from app.services.postgresql_profiling_connection_authorization import (
    PostgreSQLProfilingConnectionSnapshot,
)
from app.services.postgresql_profiling_credential_authorization import (
    PostgreSQLProfilingAccountApproval,
)
from app.services.postgresql_profiling_execution_policy import (
    PostgreSQLProfilingExecutionDisabledError,
)


@pytest.fixture
def context(monkeypatch):
    source_id = uuid4()
    username = "readonly_user"

    config = DatabaseConnectionConfig(
        host="database.internal",
        port=5432,
        database="synthetic_data",
        username=username,
        ssl_mode="verify-full",
        host_address="10.20.30.40",
    )

    snapshot = PostgreSQLProfilingConnectionSnapshot(
        data_source_id=source_id,
        connection_revision=3,
        config=config,
    )

    record = SimpleNamespace(
        id=uuid4(),
        data_source_id=source_id,
        connection_revision=3,
        username=username,
        approved_by_user_id=uuid4(),
        approved_at=datetime.now(timezone.utc),
        revoked_by_user_id=None,
        revoked_at=None,
    )

    db = MagicMock()

    query = db.query.return_value
    query.filter.return_value = query
    query.execution_options.return_value = query
    query.with_for_update.return_value = query
    query.one_or_none.return_value = record

    monkeypatch.setattr(
        service,
        "settings",
        SimpleNamespace(
            postgresql_profiling_execution_enabled=True,
            dq_execution_admission_enabled=False,
        ),
    )

    return SimpleNamespace(
        db=db,
        query=query,
        source_id=source_id,
        username=username,
        snapshot=snapshot,
        record=record,
    )


def lookup(context, **overrides):
    arguments = {
        "db": context.db,
        "data_source_id": context.source_id,
        "snapshot": context.snapshot,
        "username": context.username,
    }

    arguments.update(overrides)

    return service.require_postgresql_profiling_account_approval(
        **arguments
    )


def test_disabled_gate_prevents_lookup(context, monkeypatch):
    monkeypatch.setattr(
        service,
        "settings",
        SimpleNamespace(
            postgresql_profiling_execution_enabled=False,
            dq_execution_admission_enabled=True,
        ),
    )

    with pytest.raises(PostgreSQLProfilingExecutionDisabledError):
        lookup(context)

    assert context.db.mock_calls == []


@pytest.mark.parametrize(
    "source_id",
    [None, "", "not-a-uuid", 123, True],
)
def test_invalid_source_rejected_before_lookup(context, source_id):
    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context, data_source_id=source_id)

    assert context.db.mock_calls == []


@pytest.mark.parametrize(
    "snapshot",
    [None, {}, object(), "invalid-snapshot"],
)
def test_invalid_snapshot_rejected_before_lookup(context, snapshot):
    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context, snapshot=snapshot)

    assert context.db.mock_calls == []


def test_snapshot_source_mismatch_rejected(context):
    snapshot = replace(
        context.snapshot,
        data_source_id=uuid4(),
    )

    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context, snapshot=snapshot)

    assert context.db.mock_calls == []


@pytest.mark.parametrize(
    "revision",
    [None, 0, -1, True, "3", 3.0],
)
def test_invalid_snapshot_revision_rejected(context, revision):
    snapshot = replace(
        context.snapshot,
        connection_revision=revision,
    )

    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context, snapshot=snapshot)

    assert context.db.mock_calls == []


def test_invalid_snapshot_config_rejected(context):
    snapshot = replace(context.snapshot, config=None)

    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context, snapshot=snapshot)

    assert context.db.mock_calls == []


@pytest.mark.parametrize(
    "username",
    [None, "", "   ", 123, True],
)
def test_invalid_username_rejected_before_lookup(context, username):
    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context, username=username)

    assert context.db.mock_calls == []


@pytest.mark.parametrize(
    "username",
    [
        "other_user",
        "READONLY_USER",
        " readonly_user",
        "readonly_user ",
    ],
)
def test_snapshot_username_requires_exact_match(context, username):
    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context, username=username)

    assert context.db.mock_calls == []


def test_missing_persisted_approval_rejected(context):
    context.query.one_or_none.return_value = None

    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context)


def test_revoked_approval_rejected(context):
    context.record.revoked_at = datetime.now(timezone.utc)
    context.record.revoked_by_user_id = uuid4()

    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context)


def test_inconsistent_revocation_actor_rejected(context):
    context.record.revoked_by_user_id = uuid4()

    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context)


def test_inconsistent_revocation_timestamp_rejected(context):
    context.record.revoked_at = datetime.now(timezone.utc)

    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context)


def test_persisted_source_mismatch_rejected(context):
    context.record.data_source_id = uuid4()

    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context)


@pytest.mark.parametrize(
    "revision",
    [None, 0, -1, True, "3", 3.0, 2, 4],
)
def test_invalid_or_stale_persisted_revision_rejected(
    context,
    revision,
):
    context.record.connection_revision = revision

    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context)


@pytest.mark.parametrize(
    "username",
    [
        None,
        "",
        "   ",
        123,
        True,
        "other_user",
        "READONLY_USER",
        " readonly_user",
        "readonly_user ",
    ],
)
def test_invalid_persisted_username_rejected(context, username):
    context.record.username = username

    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context)


def test_missing_approval_actor_rejected(context):
    context.record.approved_by_user_id = None

    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context)


def test_missing_approval_timestamp_rejected(context):
    context.record.approved_at = None

    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context)


def test_naive_approval_timestamp_rejected(context):
    context.record.approved_at = datetime.now()

    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context)


def test_success_returns_nonsecret_approval_snapshot(context):
    approval = lookup(context)

    assert type(approval) is PostgreSQLProfilingAccountApproval

    assert approval == PostgreSQLProfilingAccountApproval(
        data_source_id=context.source_id,
        connection_revision=3,
        username=context.username,
    )

    assert approval is not context.record


def test_lookup_refreshes_and_locks_approval(context):
    lookup(context)

    context.query.execution_options.assert_called_once_with(
        populate_existing=True,
        autoflush=False,
    )

    context.query.with_for_update.assert_called_once_with()
    context.query.one_or_none.assert_called_once_with()


def test_success_does_not_write_or_end_transaction(context):
    before = vars(context.record).copy()

    lookup(context)

    context.db.add.assert_not_called()
    context.db.delete.assert_not_called()
    context.db.flush.assert_not_called()
    context.db.commit.assert_not_called()
    context.db.rollback.assert_not_called()
    context.db.close.assert_not_called()

    assert vars(context.record) == before


def test_failure_does_not_write_or_end_transaction(context):
    context.query.one_or_none.return_value = None

    with pytest.raises(service.PostgreSQLProfilingAccountApprovalError):
        lookup(context)

    context.db.add.assert_not_called()
    context.db.delete.assert_not_called()
    context.db.flush.assert_not_called()
    context.db.commit.assert_not_called()
    context.db.rollback.assert_not_called()
    context.db.close.assert_not_called()


def test_rejection_does_not_disclose_username(
    context,
    caplog,
    capsys,
):
    marker = "synthetic-private-account-marker"

    context.record.username = marker

    with pytest.raises(
        service.PostgreSQLProfilingAccountApprovalError
    ) as captured:
        lookup(context)

    output = capsys.readouterr()

    assert marker not in str(captured.value)
    assert marker not in repr(captured.value)
    assert marker not in caplog.text
    assert marker not in output.out
    assert marker not in output.err


@pytest.mark.parametrize(
    "record_id",
    [None, "", "not-a-uuid", 123, True],
)
def test_invalid_persisted_approval_identity_rejected(
    context,
    record_id,
):
    context.record.id = record_id

    with pytest.raises(
        service.PostgreSQLProfilingAccountApprovalError
    ):
        lookup(context)


@pytest.mark.parametrize(
    "actor_id",
    [None, "", "not-a-uuid", 123, True],
)
def test_invalid_persisted_approval_actor_rejected(
    context,
    actor_id,
):
    context.record.approved_by_user_id = actor_id

    with pytest.raises(
        service.PostgreSQLProfilingAccountApprovalError
    ):
        lookup(context)


@pytest.mark.parametrize(
    "approved_at",
    [None, "", 123, True],
)
def test_invalid_persisted_approval_timestamp_rejected(
    context,
    approved_at,
):
    context.record.approved_at = approved_at

    with pytest.raises(
        service.PostgreSQLProfilingAccountApprovalError
    ):
        lookup(context)


@pytest.mark.parametrize(
    "snapshot_username",
    [None, "", "   ", 123, True],
)
def test_invalid_snapshot_username_rejected_before_lookup(
    context,
    snapshot_username,
):
    config = replace(
        context.snapshot.config,
        username=snapshot_username,
    )

    snapshot = replace(
        context.snapshot,
        config=config,
    )

    with pytest.raises(
        service.PostgreSQLProfilingAccountApprovalError
    ):
        lookup(context, snapshot=snapshot)

    assert context.db.mock_calls == []


def test_ambiguous_persisted_approval_fails_closed(
    context,
    caplog,
    capsys,
):
    from sqlalchemy.exc import MultipleResultsFound

    marker = "synthetic-private-approval-detail"

    context.query.one_or_none.side_effect = (
        MultipleResultsFound(marker)
    )

    with pytest.raises(
        service.PostgreSQLProfilingAccountApprovalError
    ) as captured:
        lookup(context)

    output = capsys.readouterr()

    assert captured.value.__suppress_context__ is True
    assert marker not in str(captured.value)
    assert marker not in repr(captured.value)
    assert marker not in caplog.text
    assert marker not in output.out
    assert marker not in output.err

    context.db.add.assert_not_called()
    context.db.delete.assert_not_called()
    context.db.flush.assert_not_called()
    context.db.commit.assert_not_called()
    context.db.rollback.assert_not_called()


def test_lookup_filters_exact_approval_identity(context):
    from app.models.postgresql_profiling_account_approval import (
        PostgreSQLProfilingAccountApprovalRecord,
    )

    model = PostgreSQLProfilingAccountApprovalRecord

    lookup(context)

    context.db.query.assert_called_once_with(model)
    context.query.filter.assert_called_once()

    actual = context.query.filter.call_args.args

    expected = (
        model.data_source_id == context.source_id,
        model.connection_revision
        == context.snapshot.connection_revision,
        model.username == context.username,
        model.revoked_at.is_(None),
    )

    assert len(actual) == len(expected)
    assert context.query.filter.call_args.kwargs == {}

    for actual_expression, expected_expression in zip(
        actual,
        expected,
    ):
        assert actual_expression.compare(expected_expression)


def test_lookup_operation_order_is_preserved(context):
    lookup(context)

    operation_names = [
        entry[0]
        for entry in context.query.mock_calls
    ]

    assert operation_names == [
        "filter",
        "execution_options",
        "with_for_update",
        "one_or_none",
    ]

    context.query.execution_options.assert_called_once_with(
        populate_existing=True,
        autoflush=False,
    )

    context.query.with_for_update.assert_called_once_with()
    context.query.one_or_none.assert_called_once_with()

    context.db.add.assert_not_called()
    context.db.flush.assert_not_called()
    context.db.commit.assert_not_called()
    context.db.rollback.assert_not_called()


def test_successful_lookup_does_not_log_account_metadata(
    context,
    caplog,
    capsys,
):
    marker = "synthetic-private-approved-account"

    config = replace(
        context.snapshot.config,
        username=marker,
    )

    snapshot = replace(
        context.snapshot,
        config=config,
    )

    context.record.username = marker

    approval = lookup(
        context,
        snapshot=snapshot,
        username=marker,
    )

    output = capsys.readouterr()

    assert approval.username == marker
    assert marker not in caplog.text
    assert marker not in output.out
    assert marker not in output.err

    context.db.add.assert_not_called()
    context.db.flush.assert_not_called()
    context.db.commit.assert_not_called()
    context.db.rollback.assert_not_called()
