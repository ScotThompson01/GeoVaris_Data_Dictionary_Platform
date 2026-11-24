"""Offline security tests for PostgreSQL profiling connection revalidation."""

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.connectors.database.base import DatabaseConnectionConfig
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

    identity = SimpleNamespace(
        data_source_id=source_id,
        host="database.internal",
        port=5432,
        database_name="synthetic_data",
        connection_revision=3,
        is_verified=True,
        verified_at=datetime.now(timezone.utc),
    )

    snapshot = authorization.PostgreSQLProfilingConnectionSnapshot(
        data_source_id=source_id,
        connection_revision=3,
        config=DatabaseConnectionConfig(
            host="database.internal",
            port=5432,
            database="synthetic_data",
            username="readonly_user",
            ssl_mode="verify-full",
            host_address="10.20.30.40",
        ),
    )

    db = Mock()

    query = Mock()
    filtered = Mock()
    refreshed = Mock()
    locked = Mock()

    db.query.return_value = query
    query.filter.return_value = filtered
    filtered.execution_options.return_value = refreshed
    refreshed.with_for_update.return_value = locked
    locked.one_or_none.return_value = identity

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
        source_id=source_id,
        identity=identity,
        snapshot=snapshot,
        db=db,
        query=query,
        filtered=filtered,
        refreshed=refreshed,
        locked=locked,
        checks=checks,
    )


def invoke(context, **overrides):
    arguments = {
        "db": context.db,
        "data_source_id": context.source_id,
        "snapshot": context.snapshot,
    }

    arguments.update(overrides)

    return authorization.revalidate_postgresql_profiling_connection(
        **arguments
    )


def assert_no_policy_checks(context):
    context.checks.configuration.assert_not_called()
    context.checks.destination.assert_not_called()
    context.checks.certificate.assert_not_called()
    context.checks.resolution.assert_not_called()


def assert_no_transaction_writes(context):
    context.db.add.assert_not_called()
    context.db.flush.assert_not_called()
    context.db.commit.assert_not_called()
    context.db.rollback.assert_not_called()
    context.db.delete.assert_not_called()
    context.db.merge.assert_not_called()


def test_disabled_profiling_rejected_before_metadata_access(
    context,
    monkeypatch,
):
    monkeypatch.setattr(
        authorization.settings,
        "postgresql_profiling_execution_enabled",
        False,
    )

    with pytest.raises(PostgreSQLProfilingExecutionDisabledError):
        invoke(context)

    context.db.query.assert_not_called()
    context.db.get.assert_not_called()
    assert_no_policy_checks(context)


@pytest.mark.parametrize(
    "source_id",
    [None, "", "not-a-uuid", 123, True],
)
def test_invalid_source_identifier_rejected(context, source_id):
    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context, data_source_id=source_id)

    context.db.query.assert_not_called()
    assert_no_policy_checks(context)


@pytest.mark.parametrize(
    "snapshot",
    [None, {}, "invalid", 123],
)
def test_invalid_snapshot_rejected(context, snapshot):
    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context, snapshot=snapshot)

    context.db.query.assert_not_called()
    assert_no_policy_checks(context)


def test_snapshot_source_mismatch_rejected(context):
    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context, data_source_id=uuid4())

    context.db.query.assert_not_called()
    assert_no_policy_checks(context)


@pytest.mark.parametrize(
    "revision",
    [None, 0, -1, True, "3", 3.0],
)
def test_invalid_snapshot_revision_rejected(context, revision):
    snapshot = replace(
        context.snapshot,
        connection_revision=revision,
    )

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context, snapshot=snapshot)

    context.db.query.assert_not_called()
    assert_no_policy_checks(context)


def test_invalid_snapshot_configuration_rejected(context):
    snapshot = replace(context.snapshot, config=None)

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context, snapshot=snapshot)

    context.db.query.assert_not_called()
    assert_no_policy_checks(context)


@pytest.mark.parametrize(
    "ssl_mode",
    [None, "disable", "prefer", "require", "verify-ca"],
)
def test_insecure_snapshot_tls_mode_rejected(context, ssl_mode):
    snapshot = replace(
        context.snapshot,
        config=replace(
            context.snapshot.config,
            ssl_mode=ssl_mode,
        ),
    )

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context, snapshot=snapshot)

    context.db.query.assert_not_called()
    assert_no_policy_checks(context)


def test_missing_registered_identity_rejected(context):
    context.locked.one_or_none.return_value = None

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context)

    assert_no_policy_checks(context)


def test_current_identity_source_mismatch_rejected(context):
    context.identity.data_source_id = uuid4()

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context)

    assert_no_policy_checks(context)


@pytest.mark.parametrize(
    "attribute,value",
    [
        ("connection_revision", 4),
        ("connection_revision", 2),
        ("connection_revision", True),
        ("connection_revision", 3.0),
        ("host", "changed.internal"),
        ("port", 6543),
        ("port", 5432.0),
        ("database_name", "changed_database"),
    ],
)
def test_changed_registered_connection_rejected(
    context,
    attribute,
    value,
):
    setattr(context.identity, attribute, value)

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context)

    assert_no_policy_checks(context)


@pytest.mark.parametrize(
    "verified",
    [False, None, 1, "true"],
)
def test_revoked_verification_rejected(context, verified):
    context.identity.is_verified = verified

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context)

    assert_no_policy_checks(context)


def test_missing_verification_timestamp_rejected(context):
    context.identity.verified_at = None

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context)

    assert_no_policy_checks(context)


def test_current_verification_policy_failure_rejected(context):
    context.checks.configuration.side_effect = (
        policy.PostgreSQLVerificationPolicyError(
            "Verification policy disabled."
        )
    )

    with pytest.raises(policy.PostgreSQLVerificationPolicyError):
        invoke(context)

    context.checks.destination.assert_not_called()
    context.checks.certificate.assert_not_called()
    context.checks.resolution.assert_not_called()


def test_current_destination_policy_failure_rejected(context):
    context.checks.destination.side_effect = (
        policy.PostgreSQLVerificationPolicyError(
            "Destination no longer approved."
        )
    )

    with pytest.raises(policy.PostgreSQLVerificationPolicyError):
        invoke(context)

    context.checks.certificate.assert_not_called()
    context.checks.resolution.assert_not_called()


def test_current_certificate_failure_rejected(context):
    context.checks.certificate.side_effect = (
        policy.PostgreSQLVerificationPolicyError(
            "Trusted CA unavailable."
        )
    )

    with pytest.raises(policy.PostgreSQLVerificationPolicyError):
        invoke(context)

    context.checks.resolution.assert_not_called()


def test_current_ip_policy_failure_rejected(context):
    context.checks.resolution.side_effect = (
        policy.PostgreSQLVerificationPolicyError(
            "Resolved IP no longer approved."
        )
    )

    with pytest.raises(policy.PostgreSQLVerificationPolicyError):
        invoke(context)


def test_changed_approved_ip_rejected(context):
    context.checks.resolution.return_value = "10.20.30.41"

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context)


def test_success_requires_fresh_locked_metadata(context):
    result = invoke(context)

    assert result is None

    context.db.query.assert_called_once_with(
        PostgreSQLConnectionIdentity
    )

    context.query.filter.assert_called_once()

    predicate = context.query.filter.call_args.args[0]

    expected = (
        PostgreSQLConnectionIdentity.data_source_id
        == context.source_id
    )

    assert predicate.compare(expected)

    context.filtered.execution_options.assert_called_once_with(
        populate_existing=True,
        autoflush=False,
    )

    context.refreshed.with_for_update.assert_called_once_with()
    context.locked.one_or_none.assert_called_once_with()

    context.db.get.assert_not_called()

    assert_no_transaction_writes(context)


def test_success_reapplies_current_destination_policy(context):
    assert invoke(context) is None

    context.checks.configuration.assert_called_once_with(
        authorization.settings
    )

    context.checks.destination.assert_called_once_with(
        host="database.internal",
        port=5432,
        allowed_destinations="database.internal:5432",
    )

    context.checks.certificate.assert_called_once_with(
        "/synthetic/ca.pem"
    )

    context.checks.resolution.assert_called_once_with(
        host="database.internal",
        port=5432,
        allowed_networks="10.20.30.0/24",
    )

    assert_no_transaction_writes(context)


def test_revalidation_does_not_require_dq_admission(context):
    assert authorization.settings.dq_execution_admission_enabled is False
    assert invoke(context) is None


def test_metadata_lookup_failure_propagates(context):
    context.locked.one_or_none.side_effect = RuntimeError(
        "Synthetic metadata lookup failure."
    )

    with pytest.raises(RuntimeError, match="Synthetic metadata"):
        invoke(context)

    assert_no_policy_checks(context)
    assert_no_transaction_writes(context)



@pytest.mark.parametrize(
    "source_id",
    [None, "", "not-a-uuid", 123, True],
)
def test_invalid_snapshot_source_identity_rejected(
    context,
    source_id,
):
    snapshot = replace(
        context.snapshot,
        data_source_id=source_id,
    )

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context, snapshot=snapshot)

    context.db.query.assert_not_called()
    context.db.get.assert_not_called()
    assert_no_policy_checks(context)
    assert_no_transaction_writes(context)


@pytest.mark.parametrize(
    "host",
    [None, "", "   ", 123, True],
)
def test_invalid_snapshot_hostname_rejected(context, host):
    snapshot = replace(
        context.snapshot,
        config=replace(
            context.snapshot.config,
            host=host,
        ),
    )

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context, snapshot=snapshot)

    context.db.query.assert_not_called()
    assert_no_policy_checks(context)
    assert_no_transaction_writes(context)


@pytest.mark.parametrize(
    "port",
    [None, 0, -1, 65536, True, "5432", 5432.0],
)
def test_invalid_snapshot_port_rejected(context, port):
    snapshot = replace(
        context.snapshot,
        config=replace(
            context.snapshot.config,
            port=port,
        ),
    )

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context, snapshot=snapshot)

    context.db.query.assert_not_called()
    assert_no_policy_checks(context)
    assert_no_transaction_writes(context)


@pytest.mark.parametrize(
    "database",
    [None, "", "   ", 123, True],
)
def test_invalid_snapshot_database_rejected(
    context,
    database,
):
    snapshot = replace(
        context.snapshot,
        config=replace(
            context.snapshot.config,
            database=database,
        ),
    )

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context, snapshot=snapshot)

    context.db.query.assert_not_called()
    assert_no_policy_checks(context)
    assert_no_transaction_writes(context)


@pytest.mark.parametrize(
    "username",
    [None, "", "   ", 123, True],
)
def test_invalid_snapshot_username_rejected(
    context,
    username,
):
    snapshot = replace(
        context.snapshot,
        config=replace(
            context.snapshot.config,
            username=username,
        ),
    )

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context, snapshot=snapshot)

    context.db.query.assert_not_called()
    assert_no_policy_checks(context)
    assert_no_transaction_writes(context)


@pytest.mark.parametrize(
    "host_address",
    [None, "", "   ", 123, True],
)
def test_invalid_snapshot_pinned_ip_rejected(
    context,
    host_address,
):
    snapshot = replace(
        context.snapshot,
        config=replace(
            context.snapshot.config,
            host_address=host_address,
        ),
    )

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context, snapshot=snapshot)

    context.db.query.assert_not_called()
    assert_no_policy_checks(context)
    assert_no_transaction_writes(context)


def test_revalidation_policy_operations_run_in_required_order(
    context,
):
    operations = []

    def configuration(*args, **kwargs):
        operations.append("configuration")

    def destination(*args, **kwargs):
        operations.append("destination")

    def certificate(*args, **kwargs):
        operations.append("certificate")

    def resolution(*args, **kwargs):
        operations.append("resolution")
        return "10.20.30.40"

    context.checks.configuration.side_effect = configuration
    context.checks.destination.side_effect = destination
    context.checks.certificate.side_effect = certificate
    context.checks.resolution.side_effect = resolution

    assert invoke(context) is None

    assert operations == [
        "configuration",
        "destination",
        "certificate",
        "resolution",
    ]

    assert_no_transaction_writes(context)


def test_changed_approved_ip_does_not_modify_transaction(
    context,
):
    context.checks.resolution.return_value = "10.20.30.41"

    original_snapshot = context.snapshot

    with pytest.raises(
        authorization.PostgreSQLProfilingConnectionAuthorizationError
    ):
        invoke(context)

    assert context.snapshot is original_snapshot
    assert context.snapshot.config.host_address == "10.20.30.40"
    assert context.snapshot.connection_revision == 3

    assert_no_transaction_writes(context)


def test_locked_metadata_lookup_precedes_policy_operations(
    context,
):
    operations = []

    def lookup():
        operations.append("locked_metadata")
        return context.identity

    def configuration(*args, **kwargs):
        operations.append("configuration")

    def destination(*args, **kwargs):
        operations.append("destination")

    def certificate(*args, **kwargs):
        operations.append("certificate")

    def resolution(*args, **kwargs):
        operations.append("resolution")
        return "10.20.30.40"

    context.locked.one_or_none.side_effect = lookup
    context.checks.configuration.side_effect = configuration
    context.checks.destination.side_effect = destination
    context.checks.certificate.side_effect = certificate
    context.checks.resolution.side_effect = resolution

    assert invoke(context) is None

    assert operations == [
        "locked_metadata",
        "configuration",
        "destination",
        "certificate",
        "resolution",
    ]

    assert_no_transaction_writes(context)
