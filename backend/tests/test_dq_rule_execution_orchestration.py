"""Isolated tests for Data Quality rule execution orchestration."""

from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from app.services.data_quality_rule_execution import execute_range_rule


def test_execution_prepares_measures_and_records_in_order():
    """Protected admission precedes start; legacy measurement stays blocked.

    The former prepare/measure/revalidate/record integration is retired.
    Complete protected measurement sequencing remains unimplemented.
    """
    import pytest

    from app.services.data_quality_execution_coordinator_sequence import (
        coordinate_protected_admission_and_start,
    )
    from app.services.data_quality_execution_capacity_policy import (
        ExecutionCapacityPolicyError,
    )

    project_id = uuid4()
    execution_id = uuid4()
    calls = []

    session_factory = Mock()
    stage_admission = Mock()
    stage_start = Mock()

    def stage_start_factory(received_execution_id):
        assert received_execution_id == execution_id
        calls.append("create_start_stage")
        return stage_start

    def committed_admission(**kwargs):
        calls.append("admission")
        assert kwargs["session_factory"] is session_factory
        assert kwargs["project_id"] == project_id
        assert kwargs["stage_admission"] is stage_admission
        return execution_id

    def committed_start(**kwargs):
        calls.append("start")
        assert kwargs["session_factory"] is session_factory
        assert kwargs["project_id"] == project_id
        assert kwargs["execution_id"] == execution_id
        assert kwargs["stage_start"] is stage_start
        return execution_id

    with patch(
        "app.services.data_quality_execution_coordinator_sequence."
        "commit_and_verify_protected_admission",
        side_effect=committed_admission,
    ) as admission, patch(
        "app.services.data_quality_execution_coordinator_sequence."
        "commit_and_verify_protected_start",
        side_effect=committed_start,
    ) as start:
        result = coordinate_protected_admission_and_start(
            session_factory=session_factory,
            project_id=project_id,
            stage_admission=stage_admission,
            stage_start_factory=stage_start_factory,
        )

    assert result == execution_id
    assert calls == ["admission", "create_start_stage", "start"]
    admission.assert_called_once()
    start.assert_called_once()

    # Coordinator sequencing alone cannot activate legacy source work.
    db = Mock()
    connector = Mock()

    with patch(
        "app.core.config.settings.dq_execution_admission_enabled",
        True,
    ), patch(
        "app.core.config.settings.dq_execution_max_concurrent",
        1,
    ), patch(
        "app.services.data_quality_rule_execution.prepare_rule_execution",
    ) as prepare, patch(
        "app.services.data_quality_rule_execution.measure_prepared_range_rule",
    ) as measure, patch(
        "app.services.data_quality_rule_execution.record_successful_execution",
    ) as record, patch(
        "app.services.postgresql_execution_authorization."
        "authorize_postgresql_execution_connection",
    ) as authorize:
        with pytest.raises(
            ExecutionCapacityPolicyError,
            match="verified protected coordination",
        ):
            execute_range_rule(
                db,
                project_id=project_id,
                rule_id=uuid4(),
                actor_user_id=uuid4(),
                config=Mock(),
                connector=connector,
            )

    prepare.assert_not_called()
    authorize.assert_not_called()
    measure.assert_not_called()
    record.assert_not_called()
    connector.measure_range.assert_not_called()

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()


def test_execution_denied_before_measurement_or_persistence():
    """Denied authorization prevents protected completion and source access."""
    import pytest
    from fastapi import HTTPException

    from app.services.data_quality_execution_protected_success import (
        stage_protected_successful_execution,
    )

    db = Mock()
    project_id = uuid4()
    execution_id = uuid4()
    actor_user_id = uuid4()
    source_id = uuid4()

    snapshot = SimpleNamespace(
        config=SimpleNamespace(
            host="approved.internal",
            port=5432,
            database="approved_db",
        ),
        connection_revision=7,
    )

    denied = HTTPException(
        status_code=403,
        detail="Forbidden",
    )

    with patch(
        "app.services.data_quality_execution_protected_success."
        "get_authorized_locked_execution",
        side_effect=denied,
    ) as authorize, patch(
        "app.services.data_quality_execution_protected_success."
        "revalidate_postgresql_execution_connection",
    ) as revalidate, patch(
        "app.services.data_quality_execution_protected_success."
        "stage_successful_execution_outcome",
    ) as stage:
        with pytest.raises(HTTPException) as exc:
            stage_protected_successful_execution(
                db,
                project_id=project_id,
                execution_id=execution_id,
                actor_user_id=actor_user_id,
                expected_source_id=source_id,
                connection_snapshot=snapshot,
                measurement=SimpleNamespace(
                    total_count=10,
                    passing_count=9,
                    violation_count=1,
                ),
                completed_at=__import__(
                    "datetime"
                ).datetime.now(__import__("datetime").timezone.utc),
            )

    assert exc.value.status_code == 403
    authorize.assert_called_once_with(
        db,
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_user_id,
    )
    db.scalar.assert_not_called()
    db.scalars.assert_not_called()
    db.query.assert_not_called()
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    revalidate.assert_not_called()
    stage.assert_not_called()

def test_measurement_failure_does_not_record_success():
    """A connector failure propagates without invoking success persistence."""
    from decimal import Decimal
    import pytest

    from app.services.data_quality_rule_execution import (
        measure_prepared_range_rule,
    )

    authorized_config = SimpleNamespace(
        host="database.internal",
        port=5432,
        database="client_data",
        username="readonly_user",
        ssl_mode="verify-full",
        host_address="10.20.30.40",
    )
    prepared = {
        "version": SimpleNamespace(
            min_value=Decimal("24.3"),
            max_value=Decimal("31.1"),
            null_allowed=False,
        ),
        "field": SimpleNamespace(field_name="latitude"),
        "source_object": SimpleNamespace(
            schema_name="public",
            object_name="locations",
        ),
    }

    connector = Mock()
    connector.measure_range.side_effect = RuntimeError(
        "sanitized_measurement_failure"
    )
    db = Mock()

    with patch(
        "app.services.data_quality_rule_execution."
        "record_successful_execution",
    ) as legacy_record, patch(
        "app.services.data_quality_execution_persistence."
        "stage_successful_execution_outcome",
    ) as stage_outcome:
        with pytest.raises(
            RuntimeError,
            match="sanitized_measurement_failure",
        ):
            measure_prepared_range_rule(
                prepared,
                config=authorized_config,
                connector=connector,
                ssl_root_cert="/approved/ca.pem",
            )

    connector.measure_range.assert_called_once_with(
        config=authorized_config,
        schema_name="public",
        object_name="locations",
        field_name="latitude",
        min_value=Decimal("24.3"),
        max_value=Decimal("31.1"),
        null_allowed=False,
        password=None,
        statement_timeout_ms=30000,
        ssl_root_cert="/approved/ca.pem",
    )

    legacy_record.assert_not_called()
    stage_outcome.assert_not_called()

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()
def test_execution_rejects_unregistered_connection_before_measurement():
    """Unregistered PostgreSQL sources fail before connection policy or I/O."""
    import pytest

    from app.models.postgresql_connection_identity import (
        PostgreSQLConnectionIdentity,
    )
    from app.services.postgresql_execution_authorization import (
        PostgreSQLExecutionAuthorizationError,
        authorize_postgresql_execution_connection,
    )

    db = Mock()
    source_id = uuid4()
    db.get.return_value = None

    with patch(
        "app.services.postgresql_verification_policy."
        "require_postgresql_verification_configuration",
    ) as verify_policy, patch(
        "app.services.postgresql_verification_policy."
        "require_approved_postgresql_destination",
    ) as destination_policy, patch(
        "app.services.postgresql_verification_policy."
        "resolve_approved_postgresql_ip",
    ) as resolve_ip:
        with pytest.raises(
            PostgreSQLExecutionAuthorizationError,
            match="connection not found",
        ):
            authorize_postgresql_execution_connection(
                db,
                data_source_id=source_id,
                username="readonly_user",
            )

    db.get.assert_called_once_with(
        PostgreSQLConnectionIdentity,
        source_id,
    )
    verify_policy.assert_not_called()
    destination_policy.assert_not_called()
    resolve_ip.assert_not_called()
    db.query.assert_not_called()
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
def test_execution_measurement_uses_authorized_connection_configuration():
    """Prepared measurement can use the registered destination, not caller input."""
    from datetime import datetime, timezone
    from decimal import Decimal

    from app.services.postgresql_execution_authorization import (
        authorize_postgresql_execution_connection,
    )
    from app.services.data_quality_rule_execution import (
        measure_prepared_range_rule,
    )

    source_id = uuid4()

    caller_config = SimpleNamespace(
        host="untrusted.example",
        port=9999,
        database="untrusted_database",
        username="readonly_user",
        ssl_mode="disable",
        host_address="192.0.2.99",
    )

    registered_identity = SimpleNamespace(
        data_source_id=source_id,
        host="database.internal",
        port=5432,
        database_name="client_data",
        connection_revision=7,
        is_verified=True,
        verified_at=datetime.now(timezone.utc),
    )

    db = Mock()
    db.get.return_value = registered_identity

    with patch(
        "app.services.postgresql_verification_policy."
        "require_postgresql_verification_configuration",
    ) as verification_policy, patch(
        "app.services.postgresql_verification_policy."
        "require_approved_postgresql_destination",
    ) as destination_policy, patch(
        "app.services.postgresql_verification_policy."
        "require_postgresql_trusted_ca_file",
    ) as ca_policy, patch(
        "app.services.postgresql_verification_policy."
        "resolve_approved_postgresql_ip",
        return_value="10.20.30.40",
    ) as ip_policy:
        snapshot = authorize_postgresql_execution_connection(
            db,
            data_source_id=source_id,
            username=caller_config.username,
        )

    db.get.assert_called_once()
    assert db.get.call_args.args[1] == source_id

    verification_policy.assert_called_once()
    destination_policy.assert_called_once()
    ca_policy.assert_called_once()
    ip_policy.assert_called_once()

    assert snapshot.connection_revision == 7
    assert snapshot.config.host == "database.internal"
    assert snapshot.config.port == 5432
    assert snapshot.config.database == "client_data"
    assert snapshot.config.username == "readonly_user"
    assert snapshot.config.ssl_mode == "verify-full"
    assert snapshot.config.host_address == "10.20.30.40"

    assert snapshot.config is not caller_config
    assert snapshot.config.host != caller_config.host
    assert snapshot.config.database != caller_config.database
    assert snapshot.config.host_address != caller_config.host_address

    prepared = {
        "version": SimpleNamespace(
            min_value=Decimal("24.3"),
            max_value=Decimal("31.1"),
            null_allowed=False,
        ),
        "field": SimpleNamespace(field_name="latitude"),
        "source_object": SimpleNamespace(
            schema_name="public",
            object_name="locations",
        ),
    }

    connector = Mock()
    measurement = SimpleNamespace(
        total_count=10,
        passing_count=10,
        violation_count=0,
    )
    connector.measure_range.return_value = measurement

    result = measure_prepared_range_rule(
        prepared,
        config=snapshot.config,
        connector=connector,
        ssl_root_cert="/approved/ca.pem",
    )

    assert result is measurement

    connector.measure_range.assert_called_once_with(
        config=snapshot.config,
        schema_name="public",
        object_name="locations",
        field_name="latitude",
        min_value=Decimal("24.3"),
        max_value=Decimal("31.1"),
        null_allowed=False,
        password=None,
        statement_timeout_ms=30000,
        ssl_root_cert="/approved/ca.pem",
    )

    passed_config = connector.measure_range.call_args.kwargs["config"]

    assert passed_config is snapshot.config
    assert passed_config is not caller_config
    assert passed_config.ssl_mode == "verify-full"
    assert passed_config.host_address == "10.20.30.40"

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()
def test_execution_rejects_missing_source_before_measurement():
    """Missing source stops real preparation before authorization or I/O."""
    import pytest
    from fastapi import HTTPException

    from app.services.data_quality_rule_execution import (
        prepare_rule_execution,
    )

    db = Mock()
    db.scalar.return_value = None

    project_id = uuid4()
    rule_id = uuid4()
    actor_user_id = uuid4()

    rule = SimpleNamespace(
        id=rule_id,
        status="active",
    )
    version = SimpleNamespace(id=uuid4(), rule_id=rule_id)
    field = SimpleNamespace(id=uuid4())
    source_object = SimpleNamespace(
        id=uuid4(),
        data_source_id=uuid4(),
    )

    with patch(
        "app.services.data_quality_rule_execution."
        "get_authorized_execution_rule",
        return_value=rule,
    ) as authorize_rule, patch(
        "app.services.data_quality_rule_execution."
        "get_active_execution_version",
        return_value=version,
    ), patch(
        "app.services.data_quality_rule_execution."
        "get_execution_field",
        return_value=field,
    ), patch(
        "app.services.data_quality_rule_execution."
        "get_execution_source_object",
        return_value=source_object,
    ), patch(
        "app.services.data_quality_rule_execution."
        "validate_execution_eligibility",
    ) as validate_rule, patch(
        "app.services.data_quality_rule_execution."
        "validate_source_eligibility",
    ) as validate_source, patch(
        "app.services.postgresql_execution_authorization."
        "authorize_postgresql_execution_connection",
    ) as authorize_connection, patch(
        "app.services.data_quality_rule_execution."
        "measure_prepared_range_rule",
    ) as measure, patch(
        "app.services.data_quality_rule_execution."
        "record_successful_execution",
    ) as record:
        with pytest.raises(HTTPException) as captured:
            prepare_rule_execution(
                db,
                project_id=project_id,
                rule_id=rule_id,
                actor_user_id=actor_user_id,
            )

    assert captured.value.status_code == 409
    assert "data source not found" in captured.value.detail.lower()

    authorize_rule.assert_called_once_with(
        db,
        project_id=project_id,
        rule_id=rule_id,
        actor_user_id=actor_user_id,
    )

    db.scalar.assert_called_once()

    validate_rule.assert_not_called()
    validate_source.assert_not_called()
    authorize_connection.assert_not_called()
    measure.assert_not_called()
    record.assert_not_called()

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()

# Phase 5D security integration batch: eight regression tests


def test_execution_forwards_approved_trusted_ca_to_measurement():
    """Prepared measurement forwards the trusted CA to the connector."""
    from decimal import Decimal

    from app.services.data_quality_rule_execution import (
        measure_prepared_range_rule,
    )

    authorized_config = SimpleNamespace(
        host="database.internal",
        port=5432,
        database="client_data",
        username="readonly_user",
        ssl_mode="verify-full",
        host_address="10.20.30.40",
    )
    prepared = {
        "version": SimpleNamespace(
            min_value=Decimal("24.3"),
            max_value=Decimal("31.1"),
            null_allowed=False,
        ),
        "field": SimpleNamespace(field_name="latitude"),
        "source_object": SimpleNamespace(
            schema_name="public",
            object_name="locations",
        ),
    }
    measurement = SimpleNamespace(
        total_count=100,
        passing_count=95,
        violation_count=5,
    )
    connector = Mock()
    connector.measure_range.return_value = measurement

    result = measure_prepared_range_rule(
        prepared,
        config=authorized_config,
        connector=connector,
        ssl_root_cert="/approved/ca.pem",
    )

    assert result is measurement

    connector.measure_range.assert_called_once_with(
        config=authorized_config,
        schema_name="public",
        object_name="locations",
        field_name="latitude",
        min_value=Decimal("24.3"),
        max_value=Decimal("31.1"),
        null_allowed=False,
        password=None,
        statement_timeout_ms=30000,
        ssl_root_cert="/approved/ca.pem",
    )

    assert authorized_config.ssl_mode == "verify-full"
    assert authorized_config.host_address == "10.20.30.40"

def test_execution_never_uses_caller_supplied_ca_path():
    """Untrusted caller TLS settings cannot activate legacy measurement."""
    import pytest

    from app.services.data_quality_execution_capacity_policy import (
        ExecutionCapacityPolicyError,
    )

    caller_config = SimpleNamespace(
        host="untrusted.example",
        port=5432,
        database="untrusted_database",
        username="readonly_user",
        ssl_root_cert="/untrusted/attacker-ca.pem",
    )
    connector = Mock()
    db = Mock()

    # Even artificially enabled capacity settings cannot replace
    # verified, committed protected coordination.
    with patch(
        "app.core.config.settings.dq_execution_admission_enabled",
        True,
    ), patch(
        "app.core.config.settings.dq_execution_max_concurrent",
        1,
    ), patch(
        "app.services.data_quality_rule_execution.prepare_rule_execution",
    ) as prepare, patch(
        "app.services.data_quality_rule_execution.measure_prepared_range_rule",
    ) as measure, patch(
        "app.services.postgresql_execution_authorization."
        "authorize_postgresql_execution_connection",
    ) as authorize:
        with pytest.raises(
            ExecutionCapacityPolicyError,
            match="verified protected coordination",
        ):
            execute_range_rule(
                db,
                project_id=uuid4(),
                rule_id=uuid4(),
                actor_user_id=uuid4(),
                config=caller_config,
                connector=connector,
            )

    assert caller_config.ssl_root_cert == "/untrusted/attacker-ca.pem"

    prepare.assert_not_called()
    authorize.assert_not_called()
    measure.assert_not_called()
    connector.measure_range.assert_not_called()

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()

def test_execution_revalidates_registered_revision_before_recording():
    """Protected success revalidates revision 7 before staging outcome."""
    from datetime import datetime, timezone

    from app.services.data_quality_execution_protected_success import (
        stage_protected_successful_execution,
    )

    project_id = uuid4()
    execution_id = uuid4()
    actor_user_id = uuid4()
    source_id = uuid4()
    rule_id = uuid4()

    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        status="running",
    )
    ownership = SimpleNamespace(
        id=uuid4(),
        execution_id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        data_source_id=source_id,
        ownership_state="reserved",
    )
    reservations = [
        SimpleNamespace(reservation_state="reserved"),
        SimpleNamespace(reservation_state="reserved"),
    ]
    snapshot = SimpleNamespace(
        config=SimpleNamespace(
            host="database.internal",
            port=5432,
            database="client_data",
        ),
        connection_revision=7,
    )
    current_identity = SimpleNamespace(
        data_source_id=source_id,
        host="database.internal",
        port=5432,
        database_name="client_data",
        connection_revision=7,
        is_verified=True,
        verified_at=datetime.now(timezone.utc),
    )

    db = Mock()
    db.scalar.return_value = ownership
    db.scalars.return_value.all.return_value = reservations
    db.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.return_value = (
        current_identity
    )

    measurement = SimpleNamespace(
        total_count=10,
        passing_count=9,
        violation_count=1,
    )
    completed_at = datetime.now(timezone.utc)

    with patch(
        "app.services.data_quality_execution_protected_success."
        "get_authorized_locked_execution",
        return_value=execution,
    ) as authorize, patch(
        "app.services.data_quality_execution_protected_success."
        "validate_protected_workload",
    ) as validate, patch(
        "app.services.data_quality_execution_protected_success."
        "stage_successful_execution_outcome",
        return_value=execution,
    ) as stage:
        result = stage_protected_successful_execution(
            db,
            project_id=project_id,
            execution_id=execution_id,
            actor_user_id=actor_user_id,
            expected_source_id=source_id,
            connection_snapshot=snapshot,
            measurement=measurement,
            completed_at=completed_at,
        )

    assert result is execution
    authorize.assert_called_once_with(
        db,
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_user_id,
    )
    validate.assert_called_once_with(
        ownership=ownership,
        reservations=reservations,
    )

    db.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.assert_called_once()
    stage.assert_called_once_with(
        db,
        execution=execution,
        measurement=measurement,
        completed_at=completed_at,
    )
    db.commit.assert_not_called()
    db.add.assert_not_called()
    db.delete.assert_not_called()

def test_execution_revalidation_uses_authorized_destination_snapshot():
    """Finalization revalidates the protected source and exact snapshot."""
    from datetime import datetime, timezone

    from app.services.data_quality_execution_protected_success import (
        stage_protected_successful_execution,
    )

    project_id = uuid4()
    execution_id = uuid4()
    actor_user_id = uuid4()
    rule_id = uuid4()
    source_id = uuid4()

    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        status="running",
    )
    ownership = SimpleNamespace(
        id=uuid4(),
        execution_id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        data_source_id=source_id,
        ownership_state="reserved",
    )
    reservations = [
        SimpleNamespace(reservation_state="reserved"),
        SimpleNamespace(reservation_state="reserved"),
    ]

    # An unrelated caller configuration must not affect the destination
    # passed to registered-connection revalidation.
    caller_config = SimpleNamespace(
        host="untrusted.example",
        port=9999,
        database="untrusted",
    )
    snapshot = SimpleNamespace(
        config=SimpleNamespace(
            host="database.internal",
            port=5432,
            database="client_data",
        ),
        connection_revision=7,
    )
    assert caller_config.host != snapshot.config.host

    measurement = SimpleNamespace(
        total_count=10,
        passing_count=9,
        violation_count=1,
    )
    completed_at = datetime.now(timezone.utc)

    db = Mock()
    db.scalar.return_value = ownership
    db.scalars.return_value.all.return_value = reservations

    with patch(
        "app.services.data_quality_execution_protected_success."
        "get_authorized_locked_execution",
        return_value=execution,
    ) as authorize, patch(
        "app.services.data_quality_execution_protected_success."
        "validate_protected_workload",
    ) as validate, patch(
        "app.services.data_quality_execution_protected_success."
        "revalidate_postgresql_execution_connection",
    ) as revalidate, patch(
        "app.services.data_quality_execution_protected_success."
        "stage_successful_execution_outcome",
        return_value=execution,
    ) as stage:
        result = stage_protected_successful_execution(
            db,
            project_id=project_id,
            execution_id=execution_id,
            actor_user_id=actor_user_id,
            expected_source_id=source_id,
            connection_snapshot=snapshot,
            measurement=measurement,
            completed_at=completed_at,
        )

    assert result is execution
    authorize.assert_called_once_with(
        db,
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_user_id,
    )
    validate.assert_called_once_with(
        ownership=ownership,
        reservations=reservations,
    )
    revalidate.assert_called_once_with(
        db,
        data_source_id=source_id,
        expected_host="database.internal",
        expected_port=5432,
        expected_database="client_data",
        expected_revision=7,
    )
    stage.assert_called_once_with(
        db,
        execution=execution,
        measurement=measurement,
        completed_at=completed_at,
    )
    db.commit.assert_not_called()
    db.add.assert_not_called()
    db.delete.assert_not_called()

def test_execution_revalidation_occurs_before_success_record():
    """Protected connection revalidation must precede success staging."""
    from datetime import datetime, timezone

    from app.services.data_quality_execution_protected_success import (
        stage_protected_successful_execution,
    )

    project_id = uuid4()
    execution_id = uuid4()
    actor_user_id = uuid4()
    source_id = uuid4()
    rule_id = uuid4()

    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        status="running",
    )
    ownership = SimpleNamespace(
        id=uuid4(),
        execution_id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        data_source_id=source_id,
        ownership_state="reserved",
    )
    reservations = [
        SimpleNamespace(reservation_state="reserved"),
        SimpleNamespace(reservation_state="reserved"),
    ]
    snapshot = SimpleNamespace(
        config=SimpleNamespace(
            host="database.internal",
            port=5432,
            database="client_data",
        ),
        connection_revision=7,
    )
    measurement = SimpleNamespace(
        total_count=10,
        passing_count=9,
        violation_count=1,
    )
    completed_at = datetime.now(timezone.utc)

    db = Mock()
    db.scalar.return_value = ownership
    db.scalars.return_value.all.return_value = reservations

    calls = []

    def check_revalidation(*args, **kwargs):
        calls.append("revalidate")
        assert args == (db,)
        assert kwargs == {
            "data_source_id": source_id,
            "expected_host": "database.internal",
            "expected_port": 5432,
            "expected_database": "client_data",
            "expected_revision": 7,
        }

    def stage_outcome(*args, **kwargs):
        calls.append("stage_outcome")
        assert args == (db,)
        assert kwargs == {
            "execution": execution,
            "measurement": measurement,
            "completed_at": completed_at,
        }
        return execution

    with patch(
        "app.services.data_quality_execution_protected_success."
        "get_authorized_locked_execution",
        return_value=execution,
    ) as authorize, patch(
        "app.services.data_quality_execution_protected_success."
        "validate_protected_workload",
    ) as validate, patch(
        "app.services.data_quality_execution_protected_success."
        "revalidate_postgresql_execution_connection",
        side_effect=check_revalidation,
    ) as revalidate, patch(
        "app.services.data_quality_execution_protected_success."
        "stage_successful_execution_outcome",
        side_effect=stage_outcome,
    ) as stage:
        result = stage_protected_successful_execution(
            db,
            project_id=project_id,
            execution_id=execution_id,
            actor_user_id=actor_user_id,
            expected_source_id=source_id,
            connection_snapshot=snapshot,
            measurement=measurement,
            completed_at=completed_at,
        )

    assert result is execution
    assert calls == ["revalidate", "stage_outcome"]

    authorize.assert_called_once_with(
        db,
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_user_id,
    )
    validate.assert_called_once_with(
        ownership=ownership,
        reservations=reservations,
    )
    revalidate.assert_called_once()
    stage.assert_called_once()

    db.commit.assert_not_called()
    db.add.assert_not_called()
    db.delete.assert_not_called()

def test_execution_rejects_changed_connection_before_recording():
    """A real connection-revision mismatch prevents protected success."""
    import pytest

    from app.services.data_quality_execution_protected_success import (
        stage_protected_successful_execution,
    )
    from app.services.postgresql_execution_authorization import (
        PostgreSQLExecutionAuthorizationError,
    )

    project_id = uuid4()
    execution_id = uuid4()
    actor_user_id = uuid4()
    source_id = uuid4()
    rule_id = uuid4()

    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        status="running",
    )
    ownership = SimpleNamespace(
        id=uuid4(),
        execution_id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        data_source_id=source_id,
        ownership_state="reserved",
    )
    reservations = [
        SimpleNamespace(reservation_state="reserved"),
        SimpleNamespace(reservation_state="reserved"),
    ]
    snapshot = SimpleNamespace(
        config=SimpleNamespace(
            host="database.internal",
            port=5432,
            database="client_data",
        ),
        connection_revision=7,
    )
    registered_connection = SimpleNamespace(
        data_source_id=source_id,
        host="database.internal",
        port=5432,
        database_name="client_data",
        connection_revision=8,
        is_verified=True,
        verified_at=object(),
    )

    db = Mock()
    db.scalar.return_value = ownership
    db.scalars.return_value.all.return_value = reservations
    db.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.return_value = (
        registered_connection
    )

    with patch(
        "app.services.data_quality_execution_protected_success."
        "get_authorized_locked_execution",
        return_value=execution,
    ) as authorize, patch(
        "app.services.data_quality_execution_protected_success."
        "validate_protected_workload",
    ) as validate, patch(
        "app.services.data_quality_execution_protected_success."
        "stage_successful_execution_outcome",
    ) as stage:
        with pytest.raises(
            PostgreSQLExecutionAuthorizationError,
            match="[Cc]hanged",
        ):
            stage_protected_successful_execution(
                db,
                project_id=project_id,
                execution_id=execution_id,
                actor_user_id=actor_user_id,
                expected_source_id=source_id,
                connection_snapshot=snapshot,
                measurement=SimpleNamespace(
                    total_count=10,
                    passing_count=9,
                    violation_count=1,
                ),
                completed_at=__import__(
                    "datetime"
                ).datetime.now(__import__("datetime").timezone.utc),
            )

    authorize.assert_called_once_with(
        db,
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_user_id,
    )
    validate.assert_called_once_with(
        ownership=ownership,
        reservations=reservations,
    )

    db.query.return_value.filter.return_value.with_for_update.assert_called_once()
    db.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.assert_called_once()

    stage.assert_not_called()
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()

def test_execution_rejects_revoked_verification_before_recording():
    """Revoked PostgreSQL verification prevents protected success."""
    import pytest

    from app.services.data_quality_execution_protected_success import (
        stage_protected_successful_execution,
    )
    from app.services.postgresql_execution_authorization import (
        PostgreSQLExecutionAuthorizationError,
    )

    project_id = uuid4()
    execution_id = uuid4()
    actor_user_id = uuid4()
    source_id = uuid4()
    rule_id = uuid4()

    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        status="running",
    )
    ownership = SimpleNamespace(
        id=uuid4(),
        execution_id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        data_source_id=source_id,
        ownership_state="reserved",
    )
    reservations = [
        SimpleNamespace(reservation_state="reserved"),
        SimpleNamespace(reservation_state="reserved"),
    ]
    snapshot = SimpleNamespace(
        config=SimpleNamespace(
            host="database.internal",
            port=5432,
            database="client_data",
        ),
        connection_revision=7,
    )
    registered_connection = SimpleNamespace(
        data_source_id=source_id,
        host="database.internal",
        port=5432,
        database_name="client_data",
        connection_revision=7,
        is_verified=False,
        verified_at=None,
    )

    db = Mock()
    db.scalar.return_value = ownership
    db.scalars.return_value.all.return_value = reservations
    db.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.return_value = (
        registered_connection
    )

    with patch(
        "app.services.data_quality_execution_protected_success."
        "get_authorized_locked_execution",
        return_value=execution,
    ) as authorize, patch(
        "app.services.data_quality_execution_protected_success."
        "validate_protected_workload",
    ) as validate, patch(
        "app.services.data_quality_execution_protected_success."
        "stage_successful_execution_outcome",
    ) as stage:
        with pytest.raises(
            PostgreSQLExecutionAuthorizationError,
            match="[Rr]evoked",
        ):
            stage_protected_successful_execution(
                db,
                project_id=project_id,
                execution_id=execution_id,
                actor_user_id=actor_user_id,
                expected_source_id=source_id,
                connection_snapshot=snapshot,
                measurement=SimpleNamespace(
                    total_count=10,
                    passing_count=9,
                    violation_count=1,
                ),
                completed_at=__import__(
                    "datetime"
                ).datetime.now(__import__("datetime").timezone.utc),
            )

    authorize.assert_called_once_with(
        db,
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_user_id,
    )
    validate.assert_called_once_with(
        ownership=ownership,
        reservations=reservations,
    )

    db.query.return_value.filter.return_value.with_for_update.assert_called_once()
    db.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.assert_called_once()

    stage.assert_not_called()
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()

def test_execution_revalidation_failure_never_records_success():
    """Removed PostgreSQL connection blocks protected success staging."""
    import pytest

    from app.services.data_quality_execution_protected_success import (
        stage_protected_successful_execution,
    )
    from app.services.postgresql_execution_authorization import (
        PostgreSQLExecutionAuthorizationError,
    )

    project_id = uuid4()
    execution_id = uuid4()
    actor_user_id = uuid4()
    source_id = uuid4()
    rule_id = uuid4()

    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        status="running",
    )
    ownership = SimpleNamespace(
        id=uuid4(),
        execution_id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        data_source_id=source_id,
        ownership_state="reserved",
    )
    reservations = [
        SimpleNamespace(reservation_state="reserved"),
        SimpleNamespace(reservation_state="reserved"),
    ]
    snapshot = SimpleNamespace(
        config=SimpleNamespace(
            host="database.internal",
            port=5432,
            database="client_data",
        ),
        connection_revision=7,
    )

    db = Mock()
    db.scalar.return_value = ownership
    db.scalars.return_value.all.return_value = reservations

    # Real revalidation query finds no registered connection.
    db.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.return_value = None

    with patch(
        "app.services.data_quality_execution_protected_success."
        "get_authorized_locked_execution",
        return_value=execution,
    ) as authorize, patch(
        "app.services.data_quality_execution_protected_success."
        "validate_protected_workload",
    ) as validate, patch(
        "app.services.data_quality_execution_protected_success."
        "stage_successful_execution_outcome",
    ) as stage:
        with pytest.raises(
            PostgreSQLExecutionAuthorizationError,
            match="[Cc]hanged or was removed",
        ):
            stage_protected_successful_execution(
                db,
                project_id=project_id,
                execution_id=execution_id,
                actor_user_id=actor_user_id,
                expected_source_id=source_id,
                connection_snapshot=snapshot,
                measurement=SimpleNamespace(
                    total_count=10,
                    passing_count=9,
                    violation_count=1,
                ),
                completed_at=__import__(
                    "datetime"
                ).datetime.now(__import__("datetime").timezone.utc),
            )

    authorize.assert_called_once_with(
        db,
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_user_id,
    )
    validate.assert_called_once_with(
        ownership=ownership,
        reservations=reservations,
    )

    db.query.return_value.filter.return_value.with_for_update.assert_called_once()
    db.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.assert_called_once()

    stage.assert_not_called()
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()