"""Read-only protected execution snapshot for Phase 5E.

Internal-only service. NOT connected to API routes or source measurements.

Callers must independently establish project authorization and use a
fresh database session after the relevant transaction has committed.

A valid snapshot is point-in-time evidence only. It does not prove
transaction history, prevent later changes, or authorize measurement.
"""

from uuid import UUID

from sqlalchemy import select

from app.models.data_quality_rule_execution import DataQualityRuleExecution
from app.models.data_quality_workload_ownership import (
    DataQualityWorkloadOwnership,
)
from app.models.data_quality_execution_capacity_reservation import (
    DataQualityExecutionCapacityReservation,
)
from app.services.data_quality_execution_release_integrity import (
    validate_protected_workload,
)


def inspect_protected_execution_snapshot(
    db,
    *,
    project_id: UUID,
    execution_id: UUID,
    expected_status: str,
) -> DataQualityRuleExecution:
    """Inspect execution and reserved protection without changing records."""
    if (
        not isinstance(project_id, UUID)
        or not isinstance(execution_id, UUID)
    ):
        raise ValueError("Invalid protected execution identity.")

    if (
        not isinstance(expected_status, str)
        or expected_status not in ("pending", "running")
    ):
        raise ValueError("Invalid expected protected execution status.")

    execution = db.scalar(
        select(DataQualityRuleExecution).where(
            DataQualityRuleExecution.id == execution_id,
            DataQualityRuleExecution.project_id == project_id,
        )
    )

    if execution is None:
        raise ValueError("Protected execution not found.")

    if (
        execution.id != execution_id
        or execution.project_id != project_id
        or not isinstance(execution.rule_id, UUID)
    ):
        raise ValueError("Protected execution identity mismatch.")

    if execution.status != expected_status:
        raise ValueError("Protected execution status mismatch.")

    ownership = db.scalar(
        select(DataQualityWorkloadOwnership).where(
            DataQualityWorkloadOwnership.execution_id == execution_id,
            DataQualityWorkloadOwnership.project_id == project_id,
        )
    )

    if ownership is None:
        raise ValueError("Protected execution ownership is missing.")

    if (
        ownership.execution_id != execution.id
        or ownership.project_id != execution.project_id
        or ownership.rule_id != execution.rule_id
    ):
        raise ValueError("Protected execution ownership identity mismatch.")

    if ownership.ownership_state != "reserved":
        raise ValueError("Protected execution ownership is not reserved.")

    reservations = list(
        db.scalars(
            select(DataQualityExecutionCapacityReservation)
            .where(
                DataQualityExecutionCapacityReservation.ownership_id
                == ownership.id
            )
            .order_by(DataQualityExecutionCapacityReservation.id)
        ).all()
    )

    validate_protected_workload(
        ownership=ownership,
        reservations=reservations,
    )

    if any(
        reservation.reservation_state != "reserved"
        for reservation in reservations
    ):
        raise ValueError("Protected execution reservations are not reserved.")

    return execution
