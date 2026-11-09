"""Protected success-finalization staging contract.

Internal transaction staging only. No source measurement, commits,
capacity releases, or API activation are permitted.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from app.services.data_quality_execution_protected_success import (
    stage_protected_successful_execution,
)


def make_context():
    project_id = uuid4()
    execution_id = uuid4()
    actor_user_id = uuid4()
    rule_id = uuid4()
    source_id = uuid4()
    ownership_id = uuid4()

    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        status="running",
    )
    ownership = SimpleNamespace(
        id=ownership_id,
        execution_id=execution_id,
        project_id=project_id,
        rule_id=rule_id,
        data_source_id=source_id,
        ownership_state="reserved",
    )
    reservations = [
        SimpleNamespace(
            reservation_state="reserved",
            reservation_scope="installation",
        ),
        SimpleNamespace(
            reservation_state="reserved",
            reservation_scope="source",
        ),
    ]
    snapshot = SimpleNamespace(
        config=SimpleNamespace(
            host="approved.internal",
            port=5432,
            database="approved_db",
        ),
        connection_revision=7,
    )
    return SimpleNamespace(
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_user_id,
        source_id=source_id,
        execution=execution,
        ownership=ownership,
        reservations=reservations,
        snapshot=snapshot,
        measurement=SimpleNamespace(
            total_count=10,
            passing_count=9,
            violation_count=1,
        ),
        completed_at=datetime(
            2026, 11, 9, 17, 0, tzinfo=timezone.utc
        ),
    )


def invoke(db, ctx):
    return stage_protected_successful_execution(
        db,
        project_id=ctx.project_id,
        execution_id=ctx.execution_id,
        actor_user_id=ctx.actor_user_id,
        expected_source_id=ctx.source_id,
        connection_snapshot=ctx.snapshot,
        measurement=ctx.measurement,
        completed_at=ctx.completed_at,
    )


def test_protection_and_connection_checks_precede_outcome_staging():
    ctx = make_context()
    db = Mock()
    db.scalar.return_value = ctx.ownership
    db.scalars.return_value.all.return_value = ctx.reservations
    calls = []

    with patch(
        "app.services.data_quality_execution_protected_success."
        "get_authorized_locked_execution",
        side_effect=lambda *a, **k: (
            calls.append("authorize_and_lock") or ctx.execution
        ),
    ) as authorize, patch(
        "app.services.data_quality_execution_protected_success."
        "validate_protected_workload",
        side_effect=lambda **k: calls.append("validate_protection"),
    ) as validate, patch(
        "app.services.data_quality_execution_protected_success."
        "revalidate_postgresql_execution_connection",
        side_effect=lambda *a, **k: calls.append("revalidate"),
    ) as revalidate, patch(
        "app.services.data_quality_execution_protected_success."
        "stage_successful_execution_outcome",
        side_effect=lambda *a, **k: (
            calls.append("stage_outcome") or ctx.execution
        ),
    ) as stage:
        result = invoke(db, ctx)

    assert result is ctx.execution
    assert calls == [
        "authorize_and_lock",
        "validate_protection",
        "revalidate",
        "stage_outcome",
    ]
    authorize.assert_called_once()
    validate.assert_called_once()
    revalidate.assert_called_once_with(
        db,
        data_source_id=ctx.source_id,
        expected_host="approved.internal",
        expected_port=5432,
        expected_database="approved_db",
        expected_revision=7,
    )
    stage.assert_called_once_with(
        db,
        execution=ctx.execution,
        measurement=ctx.measurement,
        completed_at=ctx.completed_at,
    )
    db.commit.assert_not_called()
    db.add.assert_not_called()
    db.delete.assert_not_called()


@pytest.mark.parametrize(
    "state",
    ["unresolved", "released"],
)
def test_nonreserved_ownership_blocks_success(state):
    ctx = make_context()
    ctx.ownership.ownership_state = state
    db = Mock()
    db.scalar.return_value = ctx.ownership
    db.scalars.return_value.all.return_value = ctx.reservations

    with patch(
        "app.services.data_quality_execution_protected_success."
        "get_authorized_locked_execution",
        return_value=ctx.execution,
    ), patch(
        "app.services.data_quality_execution_protected_success."
        "validate_protected_workload",
    ), patch(
        "app.services.data_quality_execution_protected_success."
        "revalidate_postgresql_execution_connection",
    ) as revalidate, patch(
        "app.services.data_quality_execution_protected_success."
        "stage_successful_execution_outcome",
    ) as stage:
        with pytest.raises(ValueError):
            invoke(db, ctx)

    revalidate.assert_not_called()
    stage.assert_not_called()
    db.commit.assert_not_called()


def test_mismatched_source_blocks_revalidation_and_staging():
    ctx = make_context()
    ctx.ownership.data_source_id = uuid4()
    db = Mock()
    db.scalar.return_value = ctx.ownership
    db.scalars.return_value.all.return_value = ctx.reservations

    with patch(
        "app.services.data_quality_execution_protected_success."
        "get_authorized_locked_execution",
        return_value=ctx.execution,
    ), patch(
        "app.services.data_quality_execution_protected_success."
        "validate_protected_workload",
    ), patch(
        "app.services.data_quality_execution_protected_success."
        "revalidate_postgresql_execution_connection",
    ) as revalidate, patch(
        "app.services.data_quality_execution_protected_success."
        "stage_successful_execution_outcome",
    ) as stage:
        with pytest.raises(ValueError):
            invoke(db, ctx)

    revalidate.assert_not_called()
    stage.assert_not_called()


def test_connection_revalidation_failure_prevents_success():
    ctx = make_context()
    db = Mock()
    db.scalar.return_value = ctx.ownership
    db.scalars.return_value.all.return_value = ctx.reservations
    original_error = ValueError("Connection verification revoked")

    with patch(
        "app.services.data_quality_execution_protected_success."
        "get_authorized_locked_execution",
        return_value=ctx.execution,
    ), patch(
        "app.services.data_quality_execution_protected_success."
        "validate_protected_workload",
    ), patch(
        "app.services.data_quality_execution_protected_success."
        "revalidate_postgresql_execution_connection",
        side_effect=original_error,
    ), patch(
        "app.services.data_quality_execution_protected_success."
        "stage_successful_execution_outcome",
    ) as stage:
        with pytest.raises(ValueError) as captured:
            invoke(db, ctx)

    assert captured.value is original_error
    stage.assert_not_called()
    db.commit.assert_not_called()


def test_missing_ownership_prevents_revalidation_and_staging():
    ctx = make_context()
    db = Mock()
    db.scalar.return_value = None

    with patch(
        "app.services.data_quality_execution_protected_success."
        "get_authorized_locked_execution",
        return_value=ctx.execution,
    ), patch(
        "app.services.data_quality_execution_protected_success."
        "revalidate_postgresql_execution_connection",
    ) as revalidate, patch(
        "app.services.data_quality_execution_protected_success."
        "stage_successful_execution_outcome",
    ) as stage:
        with pytest.raises(ValueError):
            invoke(db, ctx)

    revalidate.assert_not_called()
    stage.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "invalid_snapshot",
    [
        None,
        SimpleNamespace(config=None, connection_revision=7),
        SimpleNamespace(
            config=SimpleNamespace(
                host="", port=5432, database="approved_db"
            ),
            connection_revision=7,
        ),
        SimpleNamespace(
            config=SimpleNamespace(
                host="approved.internal",
                port=True,
                database="approved_db",
            ),
            connection_revision=7,
        ),
        SimpleNamespace(
            config=SimpleNamespace(
                host="approved.internal",
                port=5432,
                database="approved_db",
            ),
            connection_revision=-1,
        ),
    ],
)
def test_invalid_connection_snapshot_rejected_before_database_access(
    invalid_snapshot,
):
    ctx = make_context()
    ctx.snapshot = invalid_snapshot
    db = Mock()

    with pytest.raises(ValueError):
        invoke(db, ctx)

    db.scalar.assert_not_called()
    db.scalars.assert_not_called()
    db.query.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "reservation_state",
    ["unresolved", "released"],
)
def test_nonreserved_reservation_blocks_success(reservation_state):
    ctx = make_context()
    ctx.reservations[0].reservation_state = reservation_state

    db = Mock()
    db.scalar.return_value = ctx.ownership
    db.scalars.return_value.all.return_value = ctx.reservations

    with patch(
        "app.services.data_quality_execution_protected_success."
        "get_authorized_locked_execution",
        return_value=ctx.execution,
    ), patch(
        "app.services.data_quality_execution_protected_success."
        "validate_protected_workload",
    ), patch(
        "app.services.data_quality_execution_protected_success."
        "revalidate_postgresql_execution_connection",
    ) as revalidate, patch(
        "app.services.data_quality_execution_protected_success."
        "stage_successful_execution_outcome",
    ) as stage:
        with pytest.raises(ValueError):
            invoke(db, ctx)

    revalidate.assert_not_called()
    stage.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "field",
    ["execution_id", "project_id", "rule_id"],
)
def test_ownership_identity_mismatch_blocks_success(field):
    ctx = make_context()
    setattr(ctx.ownership, field, uuid4())

    db = Mock()
    db.scalar.return_value = ctx.ownership
    db.scalars.return_value.all.return_value = ctx.reservations

    with patch(
        "app.services.data_quality_execution_protected_success."
        "get_authorized_locked_execution",
        return_value=ctx.execution,
    ), patch(
        "app.services.data_quality_execution_protected_success."
        "revalidate_postgresql_execution_connection",
    ) as revalidate, patch(
        "app.services.data_quality_execution_protected_success."
        "stage_successful_execution_outcome",
    ) as stage:
        with pytest.raises(ValueError):
            invoke(db, ctx)

    revalidate.assert_not_called()
    stage.assert_not_called()
    db.commit.assert_not_called()


def test_authorization_failure_blocks_protection_queries():
    ctx = make_context()
    db = Mock()
    denied = PermissionError("Execution authorization denied")

    with patch(
        "app.services.data_quality_execution_protected_success."
        "get_authorized_locked_execution",
        side_effect=denied,
    ), patch(
        "app.services.data_quality_execution_protected_success."
        "revalidate_postgresql_execution_connection",
    ) as revalidate, patch(
        "app.services.data_quality_execution_protected_success."
        "stage_successful_execution_outcome",
    ) as stage:
        with pytest.raises(PermissionError) as captured:
            invoke(db, ctx)

    assert captured.value is denied
    db.scalar.assert_not_called()
    db.scalars.assert_not_called()
    revalidate.assert_not_called()
    stage.assert_not_called()
    db.commit.assert_not_called()
