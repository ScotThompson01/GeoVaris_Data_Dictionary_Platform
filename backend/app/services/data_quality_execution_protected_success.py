"""Internal protected successful-outcome transaction staging.

NOT connected to API routes, runtime admission, or source measurement.

The caller must supply trustworthy connection evidence obtained from
an independently authorized execution workflow.

The caller owns the transaction and must commit or roll back. This
service does not establish source-workload termination or authorize
capacity release.
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
    stage_successful_execution_outcome,
)
from app.services.data_quality_execution_release_integrity import (
    validate_protected_workload,
)
from app.services.postgresql_execution_authorization import (
    revalidate_postgresql_execution_connection,
)


def stage_protected_successful_execution(
    db,
    *,
    project_id: UUID,
    execution_id: UUID,
    actor_user_id: UUID,
    expected_source_id: UUID,
    connection_snapshot,
    measurement,
    completed_at: datetime,
):
    """Stage success only after locked protection and connection checks.

    Uses the caller's open transaction. Performs no source I/O,
    independent commit, workload cancellation, or capacity release.

    This is an internal staging primitive, not a complete execution
    authorization or proof that source measurement was protected.
    """
    if any(
        not isinstance(identity, UUID)
        for identity in (
            project_id,
            execution_id,
            actor_user_id,
            expected_source_id,
        )
    ):
        raise ValueError("Invalid protected execution identity.")

    if connection_snapshot is None:
        raise ValueError("Connection authorization snapshot is required.")

    config = getattr(connection_snapshot, "config", None)
    revision = getattr(
        connection_snapshot, "connection_revision", None
    )

    if config is None:
        raise ValueError("Connection configuration snapshot is required.")

    host = getattr(config, "host", None)
    port = getattr(config, "port", None)
    database = getattr(config, "database", None)

    if (
        not isinstance(host, str)
        or not host
        or type(port) is not int
        or not 1 <= port <= 65535
        or not isinstance(database, str)
        or not database
        or type(revision) is not int
        or revision < 0
    ):
        raise ValueError("Invalid connection authorization snapshot.")

    # Authorization and execution-row locking must occur before
    # protected ownership and reservation inspection.
    execution = get_authorized_locked_execution(
        db,
        project_id=project_id,
        execution_id=execution_id,
        actor_user_id=actor_user_id,
    )

    if (
        execution.id != execution_id
        or execution.project_id != project_id
        or not isinstance(execution.rule_id, UUID)
    ):
        raise ValueError("Protected execution identity mismatch.")

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
        or ownership.data_source_id != expected_source_id
    ):
        raise ValueError(
            "Protected workload identity or source mismatch."
        )

    if ownership.ownership_state != "reserved":
        raise ValueError(
            "Successful execution requires reserved ownership."
        )

    reservations = list(
        db.scalars(
            select(DataQualityExecutionCapacityReservation)
            .where(
                DataQualityExecutionCapacityReservation.ownership_id
                == ownership.id
            )
            .order_by(DataQualityExecutionCapacityReservation.id)
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
            "Successful execution requires two reserved capacity records."
        )

    # The registered connection is revalidated under its own row lock
    # before any successful-outcome mutation.
    revalidate_postgresql_execution_connection(
        db,
        data_source_id=expected_source_id,
        expected_host=host,
        expected_port=port,
        expected_database=database,
        expected_revision=revision,
    )

    return stage_successful_execution_outcome(
        db,
        execution=execution,
        measurement=measurement,
        completed_at=completed_at,
    )
