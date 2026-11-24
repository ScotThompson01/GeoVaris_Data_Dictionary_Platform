"""Offline security tests for PostgreSQL profiling connection authorization."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.models.postgresql_connection_identity import (
    PostgreSQLConnectionIdentity,
)
from app.services import (
    postgresql_profiling_connection_authorization as authorization,
)
from app.services import postgresql_verification_policy as policy
from app.services.postgresql_profiling_execution_policy import (
    PostgreSQLProfilingExecutionDisabledError,
)


@pytest.fixture
def context(monkeypatch):
    source_id = uuid4()
    db = Mock()

    identity = SimpleNamespace(
        data_source_id=source_id,
        host="database.internal",
        port=5432,
        database_name="synthetic_data",
        connection_revision=3,
        is_verified=True,
        verified_at=datetime.now(timezone.utc),
    )

    db.get.return_value = identity

    monkeypatch.setattr(
        authorization.settings,
        "postgresql_profiling_execution_enabled",
        True,
    )
    monkeypatch.setattr(
        authorization.settings,
        "dq_execution_admission_enabled",
        False,
    )
    monkeypatch.setattr(
        authorization.settings,
        "postgresql_verification_allowed_destinations",
        "database.internal:5432",
    )
    monkeypatch.setattr(
        authorization.settings,
        "postgresql_verification_ssl_root_cert",
        "/synthetic/ca.pem",
    )
    monkeypatch.setattr(
        authorization.settings,
        "postgresql_verification_allowed_ip_networks",
        "10.20.30.0/24",
    )

    checks = SimpleNamespace(
        configuration=Mock(),
        destination=Mock(),
        certificate=Mock(),
        resolution=Mock(return_value="10.20.30.40"),
    )

    monkeypatch.setattr(
        policy,
        "require_postgresql_verification_configuration",
        checks.configuration,
    )
    monkeypatch.setattr(
        policy,
        "require_approved_postgresql_destination",
        checks.destination,
    )
    monkeypatch.setattr(
        policy,
        "require_postgresql_trusted_ca_file",
        checks.certificate,
    )
    monkeypatch.setattr(
        policy,
        "resolve_approved_postgresql_ip",
        checks.resolution,
    )

    return SimpleNamespace(
        db=db,
        source_id=source_id,
        identity=identity,
        checks=checks,
    )


def invoke(context):
    return authorization.authorize_postgresql_profiling_connection(
        db=context.db,
        data_source_id=context.source_id,
        username="readonly_user",
    )


def assert_no_policy_checks(context):
    context.checks.configuration.assert_not_called()
    context.checks.destination.assert_not_called()
    context.checks.certificate.assert_not_called()
    context.checks.resolution.assert_not_called()


def test_disabled_profiling_rejected_before_metadata_access(
    context, monkeypatch
):
    monkeypatch.setattr(
        authorization.settings,
        "postgresql_profiling_execution_enabled",
        False,
    )

    with pytest.raises(PostgreSQLProfilingExecutionDisabledError):
        invoke(context)

    context.db.get.assert_not_called()
    assert_no_policy_checks(context)


def test_missing_registered_identity_rejected(context):
    context.db.get.return_value = None

    with pytest.raises(ValueError):
        invoke(context)

    assert_no_policy_checks(context)


def test_mismatched_registered_identity_rejected(context):
    context.identity.data_source_id = uuid4()

    with pytest.raises(ValueError):
        invoke(context)

    assert_no_policy_checks(context)


@pytest.mark.parametrize("verified", [False, None, 1, "true"])
def test_nonverified_identity_rejected(context, verified):
    context.identity.is_verified = verified

    with pytest.raises(ValueError):
        invoke(context)

    assert_no_policy_checks(context)


def test_missing_verification_timestamp_rejected(context):
    context.identity.verified_at = None

    with pytest.raises(ValueError):
        invoke(context)

    assert_no_policy_checks(context)


@pytest.mark.parametrize("revision", [None, 0, -1, True, "3", 3.0])
def test_invalid_connection_revision_rejected(context, revision):
    context.identity.connection_revision = revision

    with pytest.raises(ValueError):
        invoke(context)

    assert_no_policy_checks(context)


def test_disabled_verification_policy_rejected(context, monkeypatch):
    monkeypatch.setattr(
        authorization.settings,
        "postgresql_verification_enabled",
        False,
    )

    context.checks.configuration.side_effect = (
        policy.PostgreSQLVerificationPolicyError(
            "PostgreSQL connection verification is disabled."
        )
    )

    with pytest.raises(ValueError, match="disabled"):
        invoke(context)

    context.checks.configuration.assert_called_once()
    context.checks.destination.assert_not_called()
    context.checks.certificate.assert_not_called()
    context.checks.resolution.assert_not_called()


def test_unapproved_destination_rejected_before_resolution(context):
    context.checks.destination.side_effect = (
        policy.PostgreSQLVerificationPolicyError(
            "PostgreSQL destination is not approved."
        )
    )

    with pytest.raises(ValueError, match="not approved"):
        invoke(context)

    context.checks.configuration.assert_called_once()
    context.checks.destination.assert_called_once()
    context.checks.certificate.assert_not_called()
    context.checks.resolution.assert_not_called()


def test_unavailable_certificate_rejected_before_resolution(context):
    context.checks.certificate.side_effect = (
        policy.PostgreSQLVerificationPolicyError(
            "Trusted CA certificate is unavailable."
        )
    )

    with pytest.raises(ValueError, match="unavailable"):
        invoke(context)

    context.checks.destination.assert_called_once()
    context.checks.certificate.assert_called_once()
    context.checks.resolution.assert_not_called()


def test_unapproved_resolved_ip_rejected(context):
    context.checks.resolution.side_effect = (
        policy.PostgreSQLVerificationPolicyError(
            "PostgreSQL destination IP is not approved."
        )
    )

    with pytest.raises(ValueError, match="not approved"):
        invoke(context)

    context.checks.resolution.assert_called_once()


def test_success_returns_source_bound_profiling_snapshot(context):
    snapshot = invoke(context)

    assert isinstance(
        snapshot,
        authorization.PostgreSQLProfilingConnectionSnapshot,
    )
    assert snapshot.data_source_id == context.source_id
    assert snapshot.connection_revision == 3
    assert snapshot.config.host == "database.internal"
    assert snapshot.config.port == 5432
    assert snapshot.config.database == "synthetic_data"
    assert snapshot.config.username == "readonly_user"
    assert snapshot.config.ssl_mode == "verify-full"
    assert snapshot.config.host_address == "10.20.30.40"

    context.db.get.assert_called_once_with(
        PostgreSQLConnectionIdentity,
        context.source_id,
    )

    context.checks.configuration.assert_called_once_with(
        authorization.settings,
    )
    context.checks.destination.assert_called_once_with(
        host="database.internal",
        port=5432,
        allowed_destinations="database.internal:5432",
    )
    context.checks.certificate.assert_called_once_with(
        "/synthetic/ca.pem",
    )
    context.checks.resolution.assert_called_once_with(
        host="database.internal",
        port=5432,
        allowed_networks="10.20.30.0/24",
    )

    context.db.add.assert_not_called()
    context.db.flush.assert_not_called()
    context.db.commit.assert_not_called()
    context.db.rollback.assert_not_called()
    context.db.delete.assert_not_called()


def test_profiling_connection_does_not_require_dq_admission(context):
    assert authorization.settings.dq_execution_admission_enabled is False

    snapshot = invoke(context)

    assert snapshot.data_source_id == context.source_id
    assert authorization.settings.dq_execution_admission_enabled is False



@pytest.mark.parametrize(
    "source_id",
    [None, "", "not-a-uuid", 123, True],
)
def test_invalid_source_identifier_rejected(context, source_id):
    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        authorization.authorize_postgresql_profiling_connection(
            db=context.db,
            data_source_id=source_id,
            username="readonly_user",
        )

    context.db.get.assert_not_called()
    assert_no_policy_checks(context)


@pytest.mark.parametrize(
    "username",
    [None, "", "   ", 123, True],
)
def test_invalid_username_rejected(context, username):
    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        authorization.authorize_postgresql_profiling_connection(
            db=context.db,
            data_source_id=context.source_id,
            username=username,
        )

    context.db.get.assert_not_called()
    assert_no_policy_checks(context)


@pytest.mark.parametrize(
    "host",
    [None, "", "   ", 123, True],
)
def test_invalid_registered_hostname_rejected(context, host):
    context.identity.host = host

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context)

    assert_no_policy_checks(context)


@pytest.mark.parametrize(
    "port",
    [None, 0, -1, 65536, True, "5432", 5432.0],
)
def test_invalid_registered_port_rejected(context, port):
    context.identity.port = port

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context)

    assert_no_policy_checks(context)


@pytest.mark.parametrize(
    "database",
    [None, "", "   ", 123, True],
)
def test_invalid_registered_database_rejected(context, database):
    context.identity.database_name = database

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context)

    assert_no_policy_checks(context)


def test_profiling_snapshot_is_immutable(context):
    from dataclasses import FrozenInstanceError

    snapshot = invoke(context)

    with pytest.raises(FrozenInstanceError):
        snapshot.connection_revision = 99

    with pytest.raises(FrozenInstanceError):
        snapshot.data_source_id = uuid4()

    with pytest.raises(FrozenInstanceError):
        snapshot.config = None


def test_nested_connection_configuration_is_immutable(context):
    from dataclasses import FrozenInstanceError

    snapshot = invoke(context)

    with pytest.raises(FrozenInstanceError):
        snapshot.config.host = "unapproved.internal"

    with pytest.raises(FrozenInstanceError):
        snapshot.config.host_address = "192.0.2.10"

    with pytest.raises(FrozenInstanceError):
        snapshot.config.ssl_mode = "disable"


def test_snapshot_does_not_retain_mutable_identity(context):
    snapshot = invoke(context)

    context.identity.host = "changed.internal"
    context.identity.port = 6543
    context.identity.database_name = "changed_database"
    context.identity.connection_revision = 4

    assert snapshot.config.host == "database.internal"
    assert snapshot.config.port == 5432
    assert snapshot.config.database == "synthetic_data"
    assert snapshot.connection_revision == 3


def test_snapshot_does_not_contain_password_fields(context):
    from dataclasses import asdict

    snapshot = invoke(context)
    snapshot_data = asdict(snapshot)

    forbidden_fields = {
        "password",
        "secret",
        "credentials",
        "connection_string",
        "dsn",
    }

    assert forbidden_fields.isdisjoint(snapshot_data)
    assert forbidden_fields.isdisjoint(snapshot_data["config"])
