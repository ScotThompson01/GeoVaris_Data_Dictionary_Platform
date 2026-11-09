"""Phase 5E persistence foundation for pending Data Quality executions.

Call only after execution authorization and metadata eligibility checks.
The caller owns the transaction and must commit or roll back.
This module does not access client data sources.
"""

from uuid import UUID

from app.models.data_quality_rule_execution import DataQualityRuleExecution
from app.services.data_quality_execution_lifecycle import ExecutionStatus


def stage_pending_execution(
    db,
    *,
    prepared,
    project_id: UUID,
    actor_user_id: UUID,
) -> DataQualityRuleExecution:
    """Stage a pending execution without measurements or timestamps."""

    if not isinstance(project_id, UUID):
        raise ValueError("Invalid project identity.")

    if not isinstance(actor_user_id, UUID):
        raise ValueError("Invalid actor identity.")

    if not isinstance(prepared, dict):
        raise ValueError("Invalid prepared execution metadata.")

    rule = prepared.get("rule")
    version = prepared.get("version")

    rule_id = getattr(rule, "id", None)
    version_id = getattr(version, "id", None)
    version_rule_id = getattr(version, "rule_id", None)

    if not isinstance(rule_id, UUID):
        raise ValueError("Invalid rule identity.")

    if not isinstance(version_id, UUID):
        raise ValueError("Invalid rule version identity.")

    if version_rule_id != rule_id:
        raise ValueError("Execution version does not belong to the rule.")

    execution = DataQualityRuleExecution(
        project_id=project_id,
        actor_user_id=actor_user_id,
        rule_id=rule_id,
        version_id=version_id,
        status=ExecutionStatus.PENDING.value,
        total_count=None,
        passing_count=None,
        violation_count=None,
        error_code=None,
        started_at=None,
        completed_at=None,
    )

    db.add(execution)
    db.flush()

    return execution


def stage_running_execution(
    db,
    *,
    execution: DataQualityRuleExecution,
    started_at,
) -> DataQualityRuleExecution:
    """Stage PENDING -> RUNNING without committing the transaction."""
    from datetime import datetime

    from app.services.data_quality_execution_lifecycle import (
        validate_execution_transition,
    )

    if execution is None:
        raise ValueError("An execution record is required.")

    try:
        current_status = ExecutionStatus(execution.status)
    except (ValueError, TypeError):
        raise ValueError("Unknown execution status.") from None

    validate_execution_transition(
        current_status,
        ExecutionStatus.RUNNING,
    )

    if (
        not isinstance(started_at, datetime)
        or started_at.tzinfo is None
        or started_at.utcoffset() is None
    ):
        raise ValueError("Execution start timestamp must include a timezone.")

    if execution.started_at is not None:
        raise ValueError("Execution already has a start timestamp.")

    if execution.completed_at is not None:
        raise ValueError("Pending execution cannot have a completion timestamp.")

    if any(
        value is not None
        for value in (
            execution.total_count,
            execution.passing_count,
            execution.violation_count,
        )
    ):
        raise ValueError("Pending execution cannot contain measurements.")

    if getattr(execution, "error_code", None) is not None:
        raise ValueError("Pending execution cannot contain an error code.")

    execution.status = ExecutionStatus.RUNNING.value
    execution.started_at = started_at

    db.flush()

    return execution


def get_authorized_locked_execution(
    db,
    *,
    project_id: UUID,
    execution_id: UUID,
    actor_user_id: UUID,
) -> DataQualityRuleExecution:
    """Authorize and lock a project-scoped execution within the caller's transaction.

    The caller must keep this transaction open through the state update.
    This lock does not replace a persistent source-workload lock.
    """
    from fastapi import HTTPException
    from sqlalchemy import select

    from app.services.project_authorization import require_dq_rule_executor

    require_dq_rule_executor(
        db,
        user_id=actor_user_id,
        project_id=project_id,
    )

    execution = db.scalar(
        select(DataQualityRuleExecution)
        .where(
            DataQualityRuleExecution.id == execution_id,
            DataQualityRuleExecution.project_id == project_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if execution is None:
        raise HTTPException(
            status_code=404,
            detail="Data Quality execution not found.",
        )

    return execution



def stage_authorized_running_execution(
    db,
    *,
    project_id: UUID,
    execution_id: UUID,
    actor_user_id: UUID,
    started_at,
) -> DataQualityRuleExecution:
    """Lock and stage PENDING -> RUNNING in the caller's transaction.

    Authorization and row locking precede transition validation.
    The caller must commit or roll back; this does not start source work.
    A database row lock is not a persistent source-workload lock.
    """
    execution = get_authorized_locked_execution(
        db,
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_user_id,
    )

    return stage_running_execution(
        db,
        execution=execution,
        started_at=started_at,
    )


def stage_successful_execution_outcome(
    db,
    *,
    execution: DataQualityRuleExecution,
    measurement,
    completed_at,
) -> DataQualityRuleExecution:
    """Stage RUNNING -> SUCCEEDED on the existing execution.

    Internal mutation primitive only. The caller must independently
    authorize and lock the protected execution, verify its workload
    protection, and revalidate the source connection before calling.

    This function performs no source I/O, authorization, commit,
    execution insertion, or workload capacity release.
    """
    from datetime import datetime

    from app.services.data_quality_execution_lifecycle import (
        validate_execution_transition,
    )

    if execution is None:
        raise ValueError("An existing execution record is required.")

    try:
        current_status = ExecutionStatus(execution.status)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Unknown execution status.") from None

    validate_execution_transition(
        current_status,
        ExecutionStatus.SUCCEEDED,
    )

    started_at = getattr(execution, "started_at", None)

    if (
        not isinstance(started_at, datetime)
        or started_at.tzinfo is None
        or started_at.utcoffset() is None
    ):
        raise ValueError(
            "Running execution requires a timezone-aware start timestamp."
        )

    if (
        not isinstance(completed_at, datetime)
        or completed_at.tzinfo is None
        or completed_at.utcoffset() is None
        or completed_at < started_at
    ):
        raise ValueError(
            "Execution completion must be timezone-aware and "
            "not precede its start."
        )

    if getattr(execution, "completed_at", None) is not None:
        raise ValueError("Execution already has a completion timestamp.")

    if any(
        getattr(execution, field, None) is not None
        for field in (
            "total_count",
            "passing_count",
            "violation_count",
            "error_code",
        )
    ):
        raise ValueError(
            "Running execution already contains outcome data."
        )

    total = getattr(measurement, "total_count", None)
    passing = getattr(measurement, "passing_count", None)
    violations = getattr(measurement, "violation_count", None)

    if any(
        type(value) is not int or value < 0
        for value in (total, passing, violations)
    ):
        raise ValueError(
            "Execution counts must be nonnegative integers."
        )

    if total != passing + violations:
        raise ValueError("Execution counts must balance.")

    # All validation precedes mutation to prevent partially staged
    # outcomes when supplied evidence is invalid.
    execution.total_count = total
    execution.passing_count = passing
    execution.violation_count = violations
    execution.completed_at = completed_at
    execution.status = ExecutionStatus.SUCCEEDED.value
    execution.error_code = None

    db.flush()
    return execution
