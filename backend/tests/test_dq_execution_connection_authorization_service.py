"""Fail-closed contract tests for execution connection authorization staging.

The intended service is internal-only and caller-transaction-owned.
These tests do not access source systems or execute measurements.
"""

from unittest.mock import Mock
from uuid import uuid4

import pytest


@pytest.mark.parametrize(
    "invalid_parameter",
    ("execution_id", "project_id", "data_source_id"),
)
def test_invalid_identifier_rejected_before_database_access(
    invalid_parameter,
):
    from app.services.data_quality_execution_connection_authorization import (
        stage_execution_connection_authorization,
    )

    db = Mock()
    identifiers = {
        "execution_id": uuid4(),
        "project_id": uuid4(),
        "data_source_id": uuid4(),
    }
    identifiers[invalid_parameter] = "not-a-uuid"

    with pytest.raises(ValueError):
        stage_execution_connection_authorization(
            db,
            **identifiers,
            snapshot=None,
        )

    db.assert_not_called()
    db.get.assert_not_called()
    db.query.assert_not_called()
    db.execute.assert_not_called()
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


@pytest.mark.parametrize(
    "invalid_snapshot",
    (None, "", object()),
)
def test_invalid_snapshot_rejected_before_database_access(
    invalid_snapshot,
):
    from app.services.data_quality_execution_connection_authorization import (
        stage_execution_connection_authorization,
    )

    db = Mock()

    with pytest.raises(ValueError):
        stage_execution_connection_authorization(
            db,
            execution_id=uuid4(),
            project_id=uuid4(),
            data_source_id=uuid4(),
            snapshot=invalid_snapshot,
        )

    db.get.assert_not_called()
    db.query.assert_not_called()
    db.execute.assert_not_called()
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()

@pytest.mark.parametrize(
    "invalid_ownership",
    (
        "missing",
        "execution_mismatch",
        "project_mismatch",
        "source_mismatch",
        "unresolved",
        "released",
        "inconsistent_release_audit",
    ),
)
def test_invalid_workload_ownership_rejected_under_lock(
    invalid_ownership,
):
    """Ownership must be locked and valid before any evidence is staged."""
    from types import SimpleNamespace

    from app.models.data_quality_workload_ownership import (
        DataQualityWorkloadOwnership,
    )
    from app.services.data_quality_execution_connection_authorization import (
        stage_execution_connection_authorization,
    )
    from app.services.postgresql_execution_authorization import (
        PostgreSQLExecutionConnectionSnapshot,
    )

    execution_id = uuid4()
    project_id = uuid4()
    data_source_id = uuid4()

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

    if invalid_ownership == "missing":
        ownership = None
    elif invalid_ownership == "execution_mismatch":
        ownership.execution_id = uuid4()
    elif invalid_ownership == "project_mismatch":
        ownership.project_id = uuid4()
    elif invalid_ownership == "source_mismatch":
        ownership.data_source_id = uuid4()
    elif invalid_ownership == "unresolved":
        ownership.ownership_state = "unresolved"
    elif invalid_ownership == "released":
        ownership.ownership_state = "released"
    elif invalid_ownership == "inconsistent_release_audit":
        ownership.released_at = "synthetic-not-a-real-timestamp"

    db = Mock()
    db.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.return_value = ownership

    snapshot = PostgreSQLExecutionConnectionSnapshot(
        config=SimpleNamespace(
            host="synthetic.example.invalid",
            port=5432,
            database="synthetic_test",
            username="synthetic_user",
            ssl_mode="verify-full",
            host_address="192.0.2.10",
        ),
        connection_revision=1,
    )

    with pytest.raises(ValueError):
        stage_execution_connection_authorization(
            db,
            execution_id=execution_id,
            project_id=project_id,
            data_source_id=data_source_id,
            snapshot=snapshot,
        )

    db.query.assert_called_once_with(DataQualityWorkloadOwnership)
    db.query.return_value.filter.return_value.with_for_update.assert_called_once_with()
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()

@pytest.mark.parametrize(
    "invalid_connection",
    (
        "missing",
        "host_changed",
        "port_changed",
        "database_changed",
        "revision_changed",
        "unverified",
    ),
)
def test_registered_connection_change_rejected_under_lock(
    invalid_connection,
):
    """Never stage evidence against a missing or stale connection."""
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from app.models.data_quality_workload_ownership import (
        DataQualityWorkloadOwnership,
    )
    from app.models.postgresql_connection_identity import (
        PostgreSQLConnectionIdentity,
    )
    from app.services.data_quality_execution_connection_authorization import (
        stage_execution_connection_authorization,
    )
    from app.services.postgresql_execution_authorization import (
        PostgreSQLExecutionAuthorizationError,
        PostgreSQLExecutionConnectionSnapshot,
    )

    execution_id = uuid4()
    project_id = uuid4()
    data_source_id = uuid4()

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

    connection = SimpleNamespace(
        data_source_id=data_source_id,
        host="synthetic.example.invalid",
        port=5432,
        database_name="synthetic_test",
        connection_revision=1,
        is_verified=True,
        verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    if invalid_connection == "missing":
        connection = None
    elif invalid_connection == "host_changed":
        connection.host = "changed.example.invalid"
    elif invalid_connection == "port_changed":
        connection.port = 5433
    elif invalid_connection == "database_changed":
        connection.database_name = "changed_test"
    elif invalid_connection == "revision_changed":
        connection.connection_revision = 2
    elif invalid_connection == "unverified":
        connection.is_verified = False

    snapshot = PostgreSQLExecutionConnectionSnapshot(
        config=SimpleNamespace(
            host="synthetic.example.invalid",
            port=5432,
            database="synthetic_test",
            username="synthetic_user",
            ssl_mode="verify-full",
            host_address="192.0.2.10",
        ),
        connection_revision=1,
    )

    ownership_query = Mock()
    ownership_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = ownership

    connection_query = Mock()
    connection_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = connection

    db = Mock()

    def select_query(model):
        if model is DataQualityWorkloadOwnership:
            return ownership_query
        if model is PostgreSQLConnectionIdentity:
            return connection_query
        raise AssertionError("Unexpected database model queried.")

    db.query.side_effect = select_query

    with pytest.raises(PostgreSQLExecutionAuthorizationError):
        stage_execution_connection_authorization(
            db,
            execution_id=execution_id,
            project_id=project_id,
            data_source_id=data_source_id,
            snapshot=snapshot,
        )

    assert db.query.call_count == 2
    ownership_query.filter.return_value.with_for_update.assert_called_once_with()
    connection_query.filter.return_value.with_for_update.assert_called_once_with()

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()

@pytest.mark.parametrize(
    "failure",
    (
        "configuration",
        "destination",
        "trusted_ca",
        "dns_rejected",
        "dns_changed",
    ),
)
def test_postgresql_policy_failure_blocks_authorization_staging(
    monkeypatch, failure
):
    """Security policy failures must block authorization evidence."""
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from app.models.data_quality_workload_ownership import (
        DataQualityWorkloadOwnership,
    )
    from app.models.postgresql_connection_identity import (
        PostgreSQLConnectionIdentity,
    )
    from app.services import postgresql_verification_policy as policy
    from app.services.data_quality_execution_connection_authorization import (
        stage_execution_connection_authorization,
    )
    from app.services.postgresql_execution_authorization import (
        PostgreSQLExecutionConnectionSnapshot,
    )

    execution_id = uuid4()
    project_id = uuid4()
    data_source_id = uuid4()

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

    connection = SimpleNamespace(
        data_source_id=data_source_id,
        host="synthetic.example.invalid",
        port=5432,
        database_name="synthetic_test",
        connection_revision=1,
        is_verified=True,
        verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    snapshot = PostgreSQLExecutionConnectionSnapshot(
        config=SimpleNamespace(
            host="synthetic.example.invalid",
            port=5432,
            database="synthetic_test",
            username="synthetic_user",
            ssl_mode="verify-full",
            host_address="192.0.2.10",
        ),
        connection_revision=1,
    )

    ownership_query = Mock()
    ownership_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = ownership

    connection_query = Mock()
    connection_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = connection

    db = Mock()

    def select_query(model):
        if model is DataQualityWorkloadOwnership:
            return ownership_query
        if model is PostgreSQLConnectionIdentity:
            return connection_query
        raise AssertionError("Unexpected database model queried.")

    db.query.side_effect = select_query

    checks = {
        "configuration":
            "require_postgresql_verification_configuration",
        "destination": "require_approved_postgresql_destination",
        "trusted_ca": "require_postgresql_trusted_ca_file",
        "dns_rejected": "resolve_approved_postgresql_ip",
    }

    functions = {
        "require_postgresql_verification_configuration": Mock(),
        "require_approved_postgresql_destination": Mock(),
        "require_postgresql_trusted_ca_file": Mock(),
        "resolve_approved_postgresql_ip": Mock(
            return_value="192.0.2.10"
        ),
    }

    if failure == "dns_changed":
        functions["resolve_approved_postgresql_ip"].return_value = (
            "192.0.2.11"
        )
    else:
        functions[checks[failure]].side_effect = (
            policy.PostgreSQLVerificationPolicyError(
                "Synthetic policy rejection."
            )
        )

    # Mock every policy operation: no real DNS or filesystem access.
    for name, function in functions.items():
        monkeypatch.setattr(policy, name, function)

    with pytest.raises(ValueError):
        stage_execution_connection_authorization(
            db,
            execution_id=execution_id,
            project_id=project_id,
            data_source_id=data_source_id,
            snapshot=snapshot,
        )

    assert db.query.call_count == 2
    ownership_query.filter.return_value.with_for_update.assert_called_once_with()
    connection_query.filter.return_value.with_for_update.assert_called_once_with()

    if failure == "dns_changed":
        functions["resolve_approved_postgresql_ip"].assert_called_once()
    else:
        functions[checks[failure]].assert_called_once()

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()

def test_approved_connection_evidence_staged_without_commit(monkeypatch):
    """Approved evidence is staged, never committed by the service."""
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from app.models.data_quality_execution_connection_authorization import (
        DataQualityExecutionConnectionAuthorization,
    )
    from app.models.data_quality_workload_ownership import (
        DataQualityWorkloadOwnership,
    )
    from app.models.postgresql_connection_identity import (
        PostgreSQLConnectionIdentity,
    )
    from app.services import postgresql_verification_policy as policy
    from app.services.data_quality_execution_connection_authorization import (
        stage_execution_connection_authorization,
    )
    from app.services.postgresql_execution_authorization import (
        PostgreSQLExecutionConnectionSnapshot,
    )

    execution_id = uuid4()
    project_id = uuid4()
    data_source_id = uuid4()

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

    connection = SimpleNamespace(
        data_source_id=data_source_id,
        host="synthetic.example.invalid",
        port=5432,
        database_name="synthetic_test",
        connection_revision=1,
        is_verified=True,
        verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    snapshot = PostgreSQLExecutionConnectionSnapshot(
        config=SimpleNamespace(
            host="synthetic.example.invalid",
            port=5432,
            database="synthetic_test",
            username="synthetic_user",
            ssl_mode="verify-full",
            host_address="192.0.2.10",
        ),
        connection_revision=1,
    )

    ownership_query = Mock()
    ownership_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = ownership

    connection_query = Mock()
    connection_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = connection

    db = Mock()

    def select_query(model):
        if model is DataQualityWorkloadOwnership:
            return ownership_query
        if model is PostgreSQLConnectionIdentity:
            return connection_query
        raise AssertionError("Unexpected database model queried.")

    db.query.side_effect = select_query

    policy_checks = {
        "require_postgresql_verification_configuration": Mock(),
        "require_approved_postgresql_destination": Mock(),
        "require_postgresql_trusted_ca_file": Mock(),
        "resolve_approved_postgresql_ip": Mock(
            return_value="192.0.2.10"
        ),
    }

    # Prevent any real certificate reads or DNS resolution.
    for name, check in policy_checks.items():
        monkeypatch.setattr(policy, name, check)

    before = datetime.now(timezone.utc)

    evidence = stage_execution_connection_authorization(
        db,
        execution_id=execution_id,
        project_id=project_id,
        data_source_id=data_source_id,
        snapshot=snapshot,
    )

    after = datetime.now(timezone.utc)

    assert isinstance(
        evidence, DataQualityExecutionConnectionAuthorization
    )

    assert evidence.execution_id == execution_id
    assert evidence.project_id == project_id
    assert evidence.data_source_id == data_source_id
    assert evidence.connection_revision == 1
    assert evidence.authorized_host == "synthetic.example.invalid"
    assert evidence.authorized_port == 5432
    assert evidence.authorized_database == "synthetic_test"
    assert evidence.authorized_ip == "192.0.2.10"

    assert isinstance(evidence.authorized_at, datetime)
    assert evidence.authorized_at.tzinfo is not None
    assert before <= evidence.authorized_at <= after

    assert db.query.call_count == 2
    ownership_query.filter.return_value.with_for_update.assert_called_once_with()
    connection_query.filter.return_value.with_for_update.assert_called_once_with()

    for check in policy_checks.values():
        check.assert_called_once()

    db.add.assert_called_once_with(evidence)
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()

    # Authorization evidence must not contain credentials.
    forbidden_fields = {
        "username",
        "password",
        "secret",
        "token",
        "ssl_root_cert",
        "connection_string",
    }

    assert forbidden_fields.isdisjoint(
        evidence.__table__.columns.keys()
    )

def test_duplicate_authorization_evidence_propagates_integrity_error(
    monkeypatch,
):
    """A uniqueness failure must not trigger retries or transaction control."""
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from sqlalchemy.exc import IntegrityError

    from app.models.data_quality_execution_connection_authorization import (
        DataQualityExecutionConnectionAuthorization,
    )
    from app.models.data_quality_workload_ownership import (
        DataQualityWorkloadOwnership,
    )
    from app.models.postgresql_connection_identity import (
        PostgreSQLConnectionIdentity,
    )
    from app.services import postgresql_verification_policy as policy
    from app.services.data_quality_execution_connection_authorization import (
        stage_execution_connection_authorization,
    )
    from app.services.postgresql_execution_authorization import (
        PostgreSQLExecutionConnectionSnapshot,
    )

    execution_id = uuid4()
    project_id = uuid4()
    data_source_id = uuid4()

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

    connection = SimpleNamespace(
        data_source_id=data_source_id,
        host="synthetic.example.invalid",
        port=5432,
        database_name="synthetic_test",
        connection_revision=1,
        is_verified=True,
        verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    snapshot = PostgreSQLExecutionConnectionSnapshot(
        config=SimpleNamespace(
            host="synthetic.example.invalid",
            port=5432,
            database="synthetic_test",
            username="synthetic_user",
            ssl_mode="verify-full",
            host_address="192.0.2.10",
        ),
        connection_revision=1,
    )

    ownership_query = Mock()
    ownership_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = ownership

    connection_query = Mock()
    connection_query.filter.return_value.with_for_update.return_value.one_or_none.return_value = connection

    db = Mock()

    def select_query(model):
        if model is DataQualityWorkloadOwnership:
            return ownership_query
        if model is PostgreSQLConnectionIdentity:
            return connection_query
        raise AssertionError("Unexpected database model queried.")

    db.query.side_effect = select_query

    policy_checks = {
        "require_postgresql_verification_configuration": Mock(),
        "require_approved_postgresql_destination": Mock(),
        "require_postgresql_trusted_ca_file": Mock(),
        "resolve_approved_postgresql_ip": Mock(
            return_value="192.0.2.10"
        ),
    }

    for name, check in policy_checks.items():
        monkeypatch.setattr(policy, name, check)

    db.flush.side_effect = IntegrityError(
        "synthetic insert",
        {},
        Exception("synthetic uniqueness violation"),
    )

    with pytest.raises(IntegrityError):
        stage_execution_connection_authorization(
            db,
            execution_id=execution_id,
            project_id=project_id,
            data_source_id=data_source_id,
            snapshot=snapshot,
        )

    assert db.query.call_count == 2

    ownership_query.filter.return_value.with_for_update.assert_called_once_with()
    connection_query.filter.return_value.with_for_update.assert_called_once_with()

    for check in policy_checks.values():
        check.assert_called_once()

    db.add.assert_called_once()
    evidence = db.add.call_args.args[0]

    assert isinstance(
        evidence, DataQualityExecutionConnectionAuthorization
    )
    assert evidence.execution_id == execution_id
    assert evidence.project_id == project_id
    assert evidence.data_source_id == data_source_id

    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.delete.assert_not_called()
    db.merge.assert_not_called()
