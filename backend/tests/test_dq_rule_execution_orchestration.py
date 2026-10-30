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
    }
    measurement = SimpleNamespace(
        total_count=100,
        passing_count=95,
        violation_count=5,
    )
    execution = SimpleNamespace(status="succeeded")

    calls = []

    with patch(
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
    ) as record:
        result = execute_range_rule(
            db,
            project_id=project_id,
            rule_id=rule_id,
            actor_user_id=actor_user_id,
            config=config,
            password="runtime_test_secret",
        )

    assert result is execution
    assert calls == ["prepare", "measure", "record"]

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
    prepared = {"rule": SimpleNamespace(id=rule_id)}

    with patch(
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
