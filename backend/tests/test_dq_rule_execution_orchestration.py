"""Isolated tests for Data Quality rule execution orchestration."""

from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from app.services.data_quality_rule_execution import execute_range_rule


def test_execution_prepares_measures_and_records_in_order():
    db = Mock()
    config = Mock()
    project_id = uuid4()
    actor_user_id = uuid4()
    rule_id = uuid4()

    prepared = {
        "rule": SimpleNamespace(id=rule_id),
        "version": SimpleNamespace(id=uuid4(), rule_id=rule_id),
        "source": SimpleNamespace(id=uuid4()),
    }
    measurement = SimpleNamespace(
        total_count=100,
        passing_count=95,
        violation_count=5,
    )
    execution = SimpleNamespace(status="succeeded")

    calls = []

    with patch(
        "app.services.postgresql_execution_authorization.authorize_postgresql_execution_connection",
        return_value=SimpleNamespace(config=config, connection_revision=1),
    ), patch(
        "app.services.data_quality_rule_execution.prepare_rule_execution",
        side_effect=lambda *args, **kwargs: (
            calls.append("prepare") or prepared
        ),
    ) as prepare, patch(
        "app.services.data_quality_rule_execution.measure_prepared_range_rule",
        side_effect=lambda *args, **kwargs: (
            calls.append("measure") or measurement
        ),
    ) as measure, patch(
        "app.services.data_quality_rule_execution.record_successful_execution",
        side_effect=lambda *args, **kwargs: (
            calls.append("record") or execution
        ),
    ) as record, patch(
        "app.services.postgresql_execution_authorization.revalidate_postgresql_execution_connection",
        side_effect=lambda *args, **kwargs: calls.append("revalidate"),
    ):
        result = execute_range_rule(
            db,
            project_id=project_id,
            rule_id=rule_id,
            actor_user_id=actor_user_id,
            config=config,
            password="runtime_test_secret",
        )

    assert result is execution
    assert calls == ["prepare", "measure", "revalidate", "record"]

    prepare.assert_called_once_with(
        db,
        project_id=project_id,
        rule_id=rule_id,
        actor_user_id=actor_user_id,
    )

    measure.assert_called_once()
    assert measure.call_args.args == (prepared,)
    assert measure.call_args.kwargs["config"] is config
    assert measure.call_args.kwargs["password"] == "runtime_test_secret"

    record.assert_called_once()
    assert record.call_args.args == (db,)
    assert record.call_args.kwargs["prepared"] is prepared
    assert record.call_args.kwargs["measurement"] is measurement
    assert record.call_args.kwargs["project_id"] == project_id
    assert record.call_args.kwargs["actor_user_id"] == actor_user_id



def test_execution_denied_before_measurement_or_persistence():
    """A denied executor must never reach the source or execution history."""
    from fastapi import HTTPException

    db = Mock()

    with patch(
        "app.services.data_quality_rule_execution.prepare_rule_execution",
        side_effect=HTTPException(status_code=403, detail="Forbidden"),
    ) as prepare, patch(
        "app.services.data_quality_rule_execution.measure_prepared_range_rule",
    ) as measure, patch(
        "app.services.data_quality_rule_execution.record_successful_execution",
    ) as record:
        import pytest

        with pytest.raises(HTTPException) as exc:
            execute_range_rule(
                db,
                project_id=uuid4(),
                rule_id=uuid4(),
                actor_user_id=uuid4(),
                config=Mock(),
            )

    assert exc.value.status_code == 403
    prepare.assert_called_once()
    measure.assert_not_called()
    record.assert_not_called()


def test_measurement_failure_does_not_record_success():
    """A failed source measurement must not produce a success record."""
    db = Mock()
    project_id = uuid4()
    rule_id = uuid4()
    actor_user_id = uuid4()
    prepared = {
        "rule": SimpleNamespace(id=rule_id),
        "source": SimpleNamespace(id=uuid4()),
    }

    with patch(
        "app.services.postgresql_execution_authorization.authorize_postgresql_execution_connection",
        return_value=SimpleNamespace(config=Mock(), connection_revision=1),
    ), patch(
        "app.services.data_quality_rule_execution.prepare_rule_execution",
        return_value=prepared,
    ) as prepare, patch(
        "app.services.data_quality_rule_execution.measure_prepared_range_rule",
        side_effect=RuntimeError("sanitized_measurement_failure"),
    ) as measure, patch(
        "app.services.data_quality_rule_execution.record_successful_execution",
    ) as record:
        import pytest

        with pytest.raises(RuntimeError, match="sanitized_measurement_failure"):
            execute_range_rule(
                db,
                project_id=project_id,
                rule_id=rule_id,
                actor_user_id=actor_user_id,
                config=Mock(),
            )

    prepare.assert_called_once()
    measure.assert_called_once()
    record.assert_not_called()

def test_execution_rejects_unregistered_connection_before_measurement():
    """Missing registered connections must never reach source measurement."""
    import pytest

    db = Mock()
    source_id = uuid4()
    prepared = {
        "source": SimpleNamespace(id=source_id),
    }

    with patch(
        "app.services.data_quality_rule_execution.prepare_rule_execution",
        return_value=prepared,
    ), patch(
        "app.services.postgresql_execution_authorization.authorize_postgresql_execution_connection",
        side_effect=ValueError("Registered PostgreSQL connection not found."),
    ) as authorize, patch(
        "app.services.data_quality_rule_execution.measure_prepared_range_rule",
    ) as measure, patch(
        "app.services.data_quality_rule_execution.record_successful_execution",
    ) as record:
        with pytest.raises(ValueError, match="connection not found"):
            execute_range_rule(
                db,
                project_id=uuid4(),
                rule_id=uuid4(),
                actor_user_id=uuid4(),
                config=Mock(),
                password="runtime_test_secret",
            )

    authorize.assert_called_once()
    measure.assert_not_called()
    record.assert_not_called()

def test_execution_measurement_uses_authorized_connection_configuration():
    """Measurement must use the registered configuration, not the caller's."""
    db = Mock()
    source_id = uuid4()
    rule_id = uuid4()
    caller_config = Mock()
    caller_config.username = "readonly_user"
    authorized_config = Mock()
    snapshot = SimpleNamespace(
        config=authorized_config,
        connection_revision=7,
    )
    prepared = {
        "source": SimpleNamespace(id=source_id),
        "rule": SimpleNamespace(id=rule_id),
    }

    with patch(
        "app.services.data_quality_rule_execution.prepare_rule_execution",
        return_value=prepared,
    ), patch(
        "app.services.postgresql_execution_authorization.authorize_postgresql_execution_connection",
        return_value=snapshot,
    ) as authorize, patch(
        "app.services.postgresql_execution_authorization.revalidate_postgresql_execution_connection",
    ), patch(
        "app.services.data_quality_rule_execution.measure_prepared_range_rule",
        return_value=SimpleNamespace(
            total_count=10,
            passing_count=10,
            violation_count=0,
        ),
    ) as measure, patch(
        "app.services.data_quality_rule_execution.record_successful_execution",
        return_value=SimpleNamespace(status="succeeded"),
    ):
        execute_range_rule(
            db,
            project_id=uuid4(),
            rule_id=rule_id,
            actor_user_id=uuid4(),
            config=caller_config,
        )

    authorize.assert_called_once_with(
        db,
        data_source_id=source_id,
        username="readonly_user",
    )
    measure.assert_called_once()
    assert measure.call_args.kwargs["config"] is authorized_config

def test_execution_rejects_missing_source_before_measurement():
    """Missing source metadata must never enable caller-config execution."""
    import pytest

    db = Mock()
    prepared = {
        "rule": SimpleNamespace(id=uuid4()),
    }

    with patch(
        "app.services.data_quality_rule_execution.prepare_rule_execution",
        return_value=prepared,
    ), patch(
        "app.services.postgresql_execution_authorization.authorize_postgresql_execution_connection",
    ) as authorize, patch(
        "app.services.data_quality_rule_execution.measure_prepared_range_rule",
    ) as measure, patch(
        "app.services.data_quality_rule_execution.record_successful_execution",
    ) as record:
        with pytest.raises(ValueError, match="source"):
            execute_range_rule(
                db,
                project_id=uuid4(),
                rule_id=uuid4(),
                actor_user_id=uuid4(),
                config=Mock(),
            )

    authorize.assert_not_called()
    measure.assert_not_called()
    record.assert_not_called()


# Phase 5D security integration batch: eight regression tests

def _security_execution_fixture():
    """Build isolated execution inputs with no client database access."""
    source_id = uuid4()
    rule_id = uuid4()
    caller_config = Mock()
    caller_config.username = "readonly_user"

    authorized_config = Mock()
    authorized_config.host = "database.internal"
    authorized_config.port = 5432
    authorized_config.database = "client_data"
    authorized_config.ssl_mode = "verify-full"
    authorized_config.host_address = "10.20.30.40"

    snapshot = SimpleNamespace(
        config=authorized_config,
        connection_revision=7,
    )
    prepared = {
        "source": SimpleNamespace(id=source_id),
        "rule": SimpleNamespace(id=rule_id),
    }
    measurement = SimpleNamespace(
        total_count=10,
        passing_count=9,
        violation_count=1,
    )
    return source_id, rule_id, caller_config, snapshot, prepared, measurement


def _run_security_execution(
    *,
    snapshot=None,
    measurement_error=None,
    revalidation_error=None,
):
    """Run orchestration with mocked authorization, measurement and persistence."""
    from contextlib import ExitStack

    source_id, rule_id, caller_config, default_snapshot, prepared, measurement = (
        _security_execution_fixture()
    )
    if snapshot is None:
        snapshot = default_snapshot

    with ExitStack() as stack:
        stack.enter_context(patch(
            "app.services.data_quality_rule_execution.prepare_rule_execution",
            return_value=prepared,
        ))
        authorize = stack.enter_context(patch(
            "app.services.postgresql_execution_authorization.authorize_postgresql_execution_connection",
            return_value=snapshot,
        ))
        measure = stack.enter_context(patch(
            "app.services.data_quality_rule_execution.measure_prepared_range_rule",
            side_effect=measurement_error,
            return_value=measurement,
        ))
        revalidate = stack.enter_context(patch(
            "app.services.postgresql_execution_authorization.revalidate_postgresql_execution_connection",
            side_effect=revalidation_error,
        ))
        record = stack.enter_context(patch(
            "app.services.data_quality_rule_execution.record_successful_execution",
            return_value=SimpleNamespace(status="succeeded"),
        ))
        settings = stack.enter_context(patch(
            "app.core.config.settings.postgresql_verification_ssl_root_cert",
            "/approved/ca.pem",
        ))

        db = Mock()
        error = None
        result = None
        try:
            result = execute_range_rule(
                db,
                project_id=uuid4(),
                rule_id=rule_id,
                actor_user_id=uuid4(),
                config=caller_config,
                password="runtime_test_secret",
            )
        except Exception as exc:
            error = exc

        return SimpleNamespace(
            db=db,
            source_id=source_id,
            snapshot=snapshot,
            prepared=prepared,
            result=result,
            error=error,
            authorize=authorize,
            measure=measure,
            revalidate=revalidate,
            record=record,
        )


def test_execution_forwards_approved_trusted_ca_to_measurement():
    result = _run_security_execution()
    assert result.error is None
    assert result.measure.call_args.kwargs["ssl_root_cert"] == "/approved/ca.pem"


def test_execution_never_uses_caller_supplied_ca_path():
    result = _run_security_execution()
    assert result.error is None
    assert result.measure.call_args.kwargs["ssl_root_cert"] == "/approved/ca.pem"
    assert result.measure.call_args.kwargs["config"] is result.snapshot.config


def test_execution_revalidates_registered_revision_before_recording():
    result = _run_security_execution()
    assert result.error is None
    result.revalidate.assert_called_once()
    assert result.revalidate.call_args.kwargs["expected_revision"] == 7
    result.record.assert_called_once()


def test_execution_revalidation_uses_authorized_destination_snapshot():
    result = _run_security_execution()
    assert result.error is None
    kwargs = result.revalidate.call_args.kwargs
    assert kwargs["data_source_id"] == result.source_id
    assert kwargs["expected_host"] == "database.internal"
    assert kwargs["expected_port"] == 5432
    assert kwargs["expected_database"] == "client_data"


def test_execution_revalidation_occurs_before_success_record():
    calls = []
    from app.services import postgresql_execution_authorization as authorization

    original_revalidate = authorization.revalidate_postgresql_execution_connection
    original_record = (
        __import__(
            "app.services.data_quality_rule_execution",
            fromlist=["record_successful_execution"],
        ).record_successful_execution
    )

    def checked_revalidate(*args, **kwargs):
        calls.append("revalidate")
        return original_revalidate(*args, **kwargs)

    def checked_record(*args, **kwargs):
        calls.append("record")
        return original_record(*args, **kwargs)

    with patch.object(
        authorization,
        "revalidate_postgresql_execution_connection",
        side_effect=lambda *args, **kwargs: calls.append("revalidate"),
    ), patch(
        "app.services.data_quality_rule_execution.record_successful_execution",
        side_effect=lambda *args, **kwargs: calls.append("record"),
    ):
        source_id, rule_id, caller_config, snapshot, prepared, measurement = (
            _security_execution_fixture()
        )
        with patch(
            "app.services.data_quality_rule_execution.prepare_rule_execution",
            return_value=prepared,
        ), patch(
            "app.services.postgresql_execution_authorization.authorize_postgresql_execution_connection",
            return_value=snapshot,
        ), patch(
            "app.services.data_quality_rule_execution.measure_prepared_range_rule",
            return_value=measurement,
        ):
            execute_range_rule(
                Mock(),
                project_id=uuid4(),
                rule_id=rule_id,
                actor_user_id=uuid4(),
                config=caller_config,
            )

    assert calls == ["revalidate", "record"]


def test_execution_rejects_changed_connection_before_recording():
    result = _run_security_execution(
        revalidation_error=ValueError(
            "Registered PostgreSQL connection changed during execution."
        ),
    )
    assert isinstance(result.error, ValueError)
    assert "changed" in str(result.error)
    result.record.assert_not_called()


def test_execution_rejects_revoked_verification_before_recording():
    result = _run_security_execution(
        revalidation_error=ValueError(
            "PostgreSQL connection verification was revoked."
        ),
    )
    assert isinstance(result.error, ValueError)
    assert "revoked" in str(result.error)
    result.record.assert_not_called()


def test_execution_revalidation_failure_never_records_success():
    result = _run_security_execution(
        revalidation_error=ValueError(
            "Registered PostgreSQL connection changed or was removed."
        ),
    )
    assert isinstance(result.error, ValueError)
    result.measure.assert_called_once()
    result.record.assert_not_called()
