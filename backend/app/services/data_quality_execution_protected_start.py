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
from app.services.data_quality_execution_capacity_locks import (
    lock_existing_execution_capacity_controls,
)
from app.services.data_quality_execution_persistence import (
    get_authorized_locked_execution,
    lock_existing_project_execution,
    stage_running_execution,
)
from app.services.project_authorization import (
    require_dq_rule_executor,
)
from app.services.data_quality_execution_release_integrity import (
    validate_protected_workload,
)


from app.services.data_quality_execution_transaction_authorization import (
    validate_locked_execution_connection_authorization,
)

def _locate_protected_execution_source(
    db,
    *,
    project_id: UUID,
    execution_id: UUID,
) -> UUID:
    """Locate a source for lock ordering, without trusting it as authority.

    This query deliberately does not acquire a row lock. The caller must
    lock capacity controls, execution, and ownership, then revalidate the
    source identity and reservation-to-control relationships.
    """
    if not isinstance(project_id, UUID):
        raise ValueError("Invalid project identity.")

    if not isinstance(execution_id, UUID):
        raise ValueError("Invalid execution identity.")

    source_id = db.scalar(
        select(DataQualityWorkloadOwnership.data_source_id)
        .where(
            DataQualityWorkloadOwnership.execution_id == execution_id,
            DataQualityWorkloadOwnership.project_id == project_id,
        )
    )

    if not isinstance(source_id, UUID):
        raise ValueError("Protected execution source is unavailable.")

    return source_id

def _lock_authorized_protected_start(
    db,
    *,
    project_id: UUID,
    execution_id: UUID,
    actor_user_id: UUID,
    expected_source_id: UUID | None = None,
):
    """Authorize, locate, then lock capacity controls before execution.

    The locator is untrusted until ownership and reservations are
    independently revalidated under their own transaction locks.
    The caller retains all locks until transaction completion.
    """
    if not isinstance(project_id, UUID):
        raise ValueError("Invalid project identity.")

    if not isinstance(execution_id, UUID):
        raise ValueError("Invalid execution identity.")

    if not isinstance(actor_user_id, UUID):
        raise ValueError("Invalid actor identity.")

    if expected_source_id is not None and not isinstance(
        expected_source_id, UUID
    ):
        raise ValueError("Invalid expected source identity.")

    require_dq_rule_executor(
        db,
        user_id=actor_user_id,
        project_id=project_id,
    )

    source_id = _locate_protected_execution_source(
        db,
        project_id=project_id,
        execution_id=execution_id,
    )

    if expected_source_id is not None and source_id != expected_source_id:
        raise ValueError("Protected execution source identity mismatch.")

    installation, source = lock_existing_execution_capacity_controls(
        db,
        data_source_id=source_id,
    )

    execution = lock_existing_project_execution(
        db,
        project_id=project_id,
        execution_id=execution_id,
    )

    return execution, source_id, installation, source

def _validate_locked_protected_workload(
    db,
    *,
    execution,
    project_id,
    execution_id,
    expected_source_id,
    installation_control,
    source_control,
):
    """Lock and validate ownership and capacity reservations."""
    ownership = db.scalar(
        select(DataQualityWorkloadOwnership)
        .where(
            DataQualityWorkloadOwnership.execution_id == execution_id,
            DataQualityWorkloadOwnership.project_id == project_id,
        )
        .execution_options(populate_existing=True)
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

    if ownership.data_source_id != expected_source_id:
        raise ValueError("Protected execution ownership source mismatch.")

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
            .execution_options(populate_existing=True)
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

    by_scope = {
        reservation.reservation_scope: reservation
        for reservation in reservations
    }

    if (
        by_scope["installation"].capacity_control_id != installation_control.id
        or by_scope["source"].capacity_control_id != source_control.id
    ):
        raise ValueError("Protected execution capacity control mismatch.")


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
    execution, source_id, installation, source = _lock_authorized_protected_start(
        db,
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_user_id,
    )

    _validate_locked_protected_workload(
        db,
        execution=execution,
        project_id=project_id,
        execution_id=execution_id,
        expected_source_id=source_id,
        installation_control=installation,
        source_control=source,
    )
    return stage_running_execution(
        db,
        execution=execution,
        started_at=started_at,
    )


def stage_connection_authorized_protected_running_execution(
    db,
    *,
    project_id: UUID,
    execution_id: UUID,
    data_source_id: UUID,
    actor_user_id: UUID,
    started_at: datetime,
):
    """Stage RUNNING after workload and connection authorization checks.

    Internal only. The caller owns the database transaction.
    No commit, retry, source connection, or worker launch occurs.
    """
    execution, source_id, installation, source = _lock_authorized_protected_start(
        db,
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_user_id,
        expected_source_id=data_source_id,
    )

    _validate_locked_protected_workload(
        db,
        execution=execution,
        project_id=project_id,
        execution_id=execution_id,
        expected_source_id=source_id,
        installation_control=installation,
        source_control=source,
    )

    validate_locked_execution_connection_authorization(
        db,
        execution_id=execution_id,
        project_id=project_id,
        data_source_id=data_source_id,
    )

    return stage_running_execution(
        db,
        execution=execution,
        started_at=started_at,
    )
