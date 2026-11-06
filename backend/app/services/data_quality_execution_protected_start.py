"""Internal protected execution-start transaction staging.

NOT connected to API routes, execution admission, or source measurement.

The caller must:
1. Complete and commit protected admission in a separate transaction.
2. Open a new transaction before invoking this service.
3. Commit the resulting RUNNING transition before source work starts.

This service verifies protection records but cannot independently establish
that a prior transaction was committed. It does not commit, launch work,
release reservations, or establish that a source workload has stopped.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from app.models.data_quality_execution_capacity_reservation import (
    DataQualityExecutionCapacityReservation,
)
from app.models.data_quality_workload_ownership import (
    DataQualityWorkloadOwnership,
)
from app.services.data_quality_execution_persistence import (
    get_authorized_locked_execution,
    stage_running_execution,
)
from app.services.data_quality_execution_release_integrity import (
    validate_protected_workload,
)


def stage_protected_running_execution(
    db,
    *,
    project_id: UUID,
    execution_id: UUID,
    actor_user_id: UUID,
    started_at: datetime,
):
    """Stage a protected PENDING -> RUNNING transition without committing.

    Authorization and execution row locking occur before protection reads.
    Workload ownership and both reservations are locked and validated.
    A separate committed admission transaction is required of the caller.
    """
    execution = get_authorized_locked_execution(
        db,
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_user_id,
    )

    ownership = db.scalar(
        select(DataQualityWorkloadOwnership)
        .where(
            DataQualityWorkloadOwnership.execution_id == execution_id,
            DataQualityWorkloadOwnership.project_id == project_id,
        )
        .with_for_update()
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
            .order_by(
                DataQualityExecutionCapacityReservation.id
            )
            .with_for_update()
        ).all()
    )

    validate_protected_workload(
        ownership=ownership,
        reservations=reservations,
    )

    if (
        len(reservations) != 2
        or any(
            reservation.reservation_state != "reserved"
            for reservation in reservations
        )
    ):
        raise ValueError(
            "Protected execution requires two active reservations."
        )

    return stage_running_execution(
        db,
        execution=execution,
        started_at=started_at,
    )
