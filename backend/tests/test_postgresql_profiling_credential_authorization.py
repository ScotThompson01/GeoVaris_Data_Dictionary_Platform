"""Offline tests for the PostgreSQL profiling credential boundary.

All identities and credential values are synthetic.

These tests do not authenticate a database account, connect to a
source database, or establish trusted account approval.
"""

from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.connectors.database.base import DatabaseConnectionConfig
from app.services import (
    postgresql_profiling_credential_authorization as service,
)
from app.services.postgresql_profiling_connection_authorization import (
    PostgreSQLProfilingConnectionSnapshot,
)
from app.services.postgresql_profiling_execution_policy import (
    PostgreSQLProfilingExecutionDisabledError,
)


@pytest.fixture
def context(monkeypatch):
    source_id = uuid4()

    config = DatabaseConnectionConfig(
        host="database.internal",
        port=5432,
        database="synthetic_data",
        username="readonly_user",
        ssl_mode="verify-full",
        host_address="10.20.30.40",
    )

    snapshot = PostgreSQLProfilingConnectionSnapshot(
        data_source_id=source_id,
        connection_revision=3,
        config=config,
    )

    approval = service.PostgreSQLProfilingAccountApproval(
        data_source_id=source_id,
        connection_revision=3,
        username="readonly_user",
    )

    monkeypatch.setattr(
        service,
        "settings",
        SimpleNamespace(
            postgresql_profiling_execution_enabled=True,
            dq_execution_admission_enabled=False,
        ),
    )

    return {
        "data_source_id": source_id,
        "snapshot": snapshot,
        "account_approval": approval,
        "username": "readonly_user",
        "password": SecretStr("synthetic-test-password"),
    }


def validate(context, **overrides):
    arguments = {**context, **overrides}

    return service.validate_postgresql_profiling_credentials(
        **arguments
    )


def test_disabled_deployment_gate_rejects_credentials(
    context, monkeypatch
):
    monkeypatch.setattr(
        service,
        "settings",
        SimpleNamespace(
            postgresql_profiling_execution_enabled=False,
            dq_execution_admission_enabled=True,
        ),
    )

    with pytest.raises(PostgreSQLProfilingExecutionDisabledError):
        validate(context)


def test_disabled_gate_precedes_invalid_credential_validation(
    context, monkeypatch
):
    monkeypatch.setattr(
        service,
        "settings",
        SimpleNamespace(
            postgresql_profiling_execution_enabled=False,
        ),
    )

    with pytest.raises(PostgreSQLProfilingExecutionDisabledError):
        validate(
            context,
            data_source_id=None,
            snapshot=None,
            account_approval=None,
            username=None,
            password=None,
        )


@pytest.mark.parametrize(
    "invalid_source_id",
    [None, "", "not-a-uuid", 123, True],
)
def test_invalid_requested_source_identity_rejected(
    context, invalid_source_id
):
    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(context, data_source_id=invalid_source_id)


@pytest.mark.parametrize(
    "invalid_snapshot",
    [None, {}, object(), "invalid-snapshot"],
)
def test_invalid_snapshot_rejected(context, invalid_snapshot):
    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(context, snapshot=invalid_snapshot)


def test_snapshot_source_mismatch_rejected(context):
    snapshot = replace(
        context["snapshot"],
        data_source_id=uuid4(),
    )

    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(context, snapshot=snapshot)


@pytest.mark.parametrize(
    "invalid_revision",
    [None, 0, -1, True, "3", 3.0],
)
def test_invalid_snapshot_revision_rejected(
    context, invalid_revision
):
    snapshot = replace(
        context["snapshot"],
        connection_revision=invalid_revision,
    )

    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(context, snapshot=snapshot)


def test_invalid_snapshot_configuration_rejected(context):
    snapshot = replace(
        context["snapshot"],
        config=None,
    )

    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(context, snapshot=snapshot)


@pytest.mark.parametrize(
    "invalid_approval",
    [None, {}, object(), "invalid-approval"],
)
def test_missing_or_invalid_account_approval_rejected(
    context, invalid_approval
):
    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(context, account_approval=invalid_approval)


def test_account_approval_source_mismatch_rejected(context):
    approval = replace(
        context["account_approval"],
        data_source_id=uuid4(),
    )

    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(context, account_approval=approval)


@pytest.mark.parametrize(
    "invalid_revision",
    [None, 0, -1, True, "3", 3.0, 4],
)
def test_invalid_or_stale_account_approval_revision_rejected(
    context, invalid_revision
):
    approval = replace(
        context["account_approval"],
        connection_revision=invalid_revision,
    )

    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(context, account_approval=approval)


@pytest.mark.parametrize(
    "invalid_username",
    [None, "", "   ", 123, True],
)
def test_invalid_requested_username_rejected(
    context, invalid_username
):
    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(context, username=invalid_username)


@pytest.mark.parametrize(
    "username",
    ["other_user", "READONLY_USER", " readonly_user", "readonly_user "],
)
def test_requested_username_must_match_snapshot_exactly(
    context, username
):
    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(context, username=username)


def test_matching_snapshot_username_is_not_sufficient(context):
    username = "unapproved_user"

    config = replace(
        context["snapshot"].config,
        username=username,
    )

    snapshot = replace(
        context["snapshot"],
        config=config,
    )

    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(
            context,
            snapshot=snapshot,
            username=username,
        )


@pytest.mark.parametrize(
    "invalid_password",
    [
        None,
        "",
        "synthetic-plaintext-password",
        b"synthetic-bytes-password",
        123,
        True,
        SecretStr(""),
    ],
)
def test_missing_or_invalid_password_rejected(
    context, invalid_password
):
    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(context, password=invalid_password)


def test_password_is_not_extracted_during_validation(
    context, monkeypatch
):
    def forbidden_extraction(self):
        pytest.fail("Credential validation extracted plaintext.")

    monkeypatch.setattr(
        SecretStr,
        "get_secret_value",
        forbidden_extraction,
    )

    assert validate(context) is None


def test_password_whitespace_is_preserved(context):
    password = SecretStr("  synthetic-password  ")

    assert validate(context, password=password) is None

    assert password.get_secret_value() == "  synthetic-password  "


def test_success_returns_no_execution_token(context):
    assert validate(context) is None


def test_success_does_not_require_dq_execution_admission(
    context
):
    assert service.settings.dq_execution_admission_enabled is False

    assert validate(context) is None


def test_validation_failure_does_not_disclose_credentials(
    context, caplog, capsys
):
    marker = "synthetic-secret-disclosure-marker"

    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ) as exc_info:
        validate(
            context,
            username="unapproved_user",
            password=SecretStr(marker),
        )

    captured = capsys.readouterr()

    assert marker not in str(exc_info.value)
    assert marker not in repr(exc_info.value)
    assert marker not in caplog.text
    assert marker not in captured.out
    assert marker not in captured.err


def test_success_does_not_disclose_credentials(
    context, caplog, capsys
):
    marker = "synthetic-success-disclosure-marker"

    assert validate(
        context,
        password=SecretStr(marker),
    ) is None

    captured = capsys.readouterr()

    assert marker not in caplog.text
    assert marker not in captured.out
    assert marker not in captured.err


def test_success_preserves_snapshot_and_approval(context):
    snapshot_before = replace(context["snapshot"])
    approval_before = replace(context["account_approval"])

    assert validate(context) is None

    assert context["snapshot"] == snapshot_before
    assert context["account_approval"] == approval_before



@pytest.mark.parametrize(
    "invalid_source_id",
    [None, "", "not-a-uuid", 123, True],
)
def test_invalid_snapshot_source_identity_rejected(
    context, invalid_source_id
):
    snapshot = replace(
        context["snapshot"],
        data_source_id=invalid_source_id,
    )

    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(context, snapshot=snapshot)


@pytest.mark.parametrize(
    "invalid_source_id",
    [None, "", "not-a-uuid", 123, True],
)
def test_invalid_approval_source_identity_rejected(
    context, invalid_source_id
):
    approval = replace(
        context["account_approval"],
        data_source_id=invalid_source_id,
    )

    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(context, account_approval=approval)


@pytest.mark.parametrize(
    "invalid_username",
    [None, "", "   ", 123, True],
)
def test_invalid_snapshot_username_rejected(
    context, invalid_username
):
    config = replace(
        context["snapshot"].config,
        username=invalid_username,
    )

    snapshot = replace(
        context["snapshot"],
        config=config,
    )

    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(context, snapshot=snapshot)


@pytest.mark.parametrize(
    "invalid_username",
    [None, "", "   ", 123, True],
)
def test_invalid_approved_username_rejected(
    context, invalid_username
):
    approval = replace(
        context["account_approval"],
        username=invalid_username,
    )

    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(context, account_approval=approval)


@pytest.mark.parametrize(
    "approved_username",
    [
        "other_user",
        "READONLY_USER",
        " readonly_user",
        "readonly_user ",
    ],
)
def test_approved_username_must_match_exactly(
    context, approved_username
):
    approval = replace(
        context["account_approval"],
        username=approved_username,
    )

    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(context, account_approval=approval)


def test_unexpected_secret_subclass_rejected(context):
    class UnexpectedSecret(SecretStr):
        def __len__(self):
            pytest.fail("Unexpected secret subclass was evaluated.")

        def get_secret_value(self):
            pytest.fail("Unexpected secret subclass was extracted.")

    password = UnexpectedSecret("synthetic-password")

    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(context, password=password)


@pytest.mark.parametrize(
    "raw_password",
    [
        " ",
        "   ",
        "\t",
        "\u00e9\u5bc6\u7801",
        " synthetic-password\t",
    ],
)
def test_nonempty_password_preserved_exactly(
    context, raw_password
):
    password = SecretStr(raw_password)

    assert validate(context, password=password) is None

    assert password.get_secret_value() == raw_password


def test_username_mismatch_does_not_disclose_identity(
    context, caplog, capsys
):
    marker = "synthetic-sensitive-username-marker"

    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ) as exc_info:
        validate(context, username=marker)

    captured = capsys.readouterr()

    assert marker not in str(exc_info.value)
    assert marker not in repr(exc_info.value)
    assert marker not in caplog.text
    assert marker not in captured.out
    assert marker not in captured.err


def test_account_approval_contains_only_nonsecret_fields(
    context
):
    from dataclasses import asdict, fields

    approval = context["account_approval"]

    assert {field.name for field in fields(approval)} == {
        "data_source_id",
        "connection_revision",
        "username",
    }

    assert set(asdict(approval)) == {
        "data_source_id",
        "connection_revision",
        "username",
    }

    assert "synthetic-test-password" not in repr(approval)


def test_account_approval_rejects_normal_attribute_mutation(
    context
):
    from dataclasses import FrozenInstanceError

    approval = context["account_approval"]

    with pytest.raises(FrozenInstanceError):
        approval.username = "different_user"

    assert approval.username == "readonly_user"


def test_matching_account_approval_cannot_override_snapshot_source(
    context
):
    other_source_id = uuid4()

    approval = replace(
        context["account_approval"],
        data_source_id=other_source_id,
    )

    with pytest.raises(
        service.PostgreSQLProfilingCredentialAuthorizationError
    ):
        validate(
            context,
            data_source_id=other_source_id,
            account_approval=approval,
        )
