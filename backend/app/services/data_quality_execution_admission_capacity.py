"""Transactional capacity checks for internal Phase 5E admission.

NOT connected to runtime execution or client-source measurements.
NOT production-authorized.

Cooperating admission and release writers must acquire capacity-control
row locks in the same order: installation, then source. Both locks must
remain held while checking limits and staging reservations.

The caller owns commit/rollback. This service never creates workloads.
"""

from uuid import UUID

from sqlalchemy import func, select

from app.models.data_quality_execution_capacity_control import (
    DataQualityExecutionCapacityControl as CapacityControl,
)
from app.models.data_quality_execution_capacity_reservation import (
    DataQualityExecutionCapacityReservation as Reservation,
)


ACTIVE_RESERVATION_STATES = ("reserved", "unresolved")


def require_locked_execution_capacity(
    db,
    *,
    data_source_id: UUID,
    installation_limit: int,
) -> tuple[CapacityControl, CapacityControl]:
    """Lock capacity controls and require an available slot in both scopes.

    Unresolved reservations continue consuming capacity. The installation
    limit must match its persisted control; configuration alone cannot
    override the database limit.

    All cooperating writers must retain the locks through transaction
    commit or rollback.
    """
    if not isinstance(data_source_id, UUID):
        raise ValueError("Invalid data source identity.")

    if type(installation_limit) is not int or installation_limit < 1:
        raise ValueError("Invalid installation capacity limit.")

    installation = db.scalar(
        select(CapacityControl)
        .where(CapacityControl.scope_type == "installation")
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if (
        installation is None
        or installation.scope_type != "installation"
        or installation.data_source_id is not None
        or type(installation.max_concurrent) is not int
        or installation.max_concurrent != installation_limit
    ):
        raise ValueError("Installation capacity control is unavailable or inconsistent.")

    source = db.scalar(
        select(CapacityControl)
        .where(
            CapacityControl.scope_type == "source",
            CapacityControl.data_source_id == data_source_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if (
        source is None
        or source.scope_type != "source"
        or source.data_source_id != data_source_id
        or type(source.max_concurrent) is not int
        or source.max_concurrent < 1
    ):
        raise ValueError("Source capacity control is unavailable or inconsistent.")

    installation_count = db.execute(
        select(func.count())
        .select_from(Reservation)
        .where(
            Reservation.capacity_control_id == installation.id,
            Reservation.reservation_scope == "installation",
            Reservation.reservation_state.in_(ACTIVE_RESERVATION_STATES),
        )
    ).scalar_one()

    source_count = db.execute(
        select(func.count())
        .select_from(Reservation)
        .where(
            Reservation.capacity_control_id == source.id,
            Reservation.reservation_scope == "source",
            Reservation.reservation_state.in_(ACTIVE_RESERVATION_STATES),
        )
    ).scalar_one()

    if (
        type(installation_count) is not int
        or installation_count < 0
        or type(source_count) is not int
        or source_count < 0
    ):
        raise ValueError("Invalid execution capacity reservation counts.")

    if (
        installation_count >= installation.max_concurrent
        or source_count >= source.max_concurrent
    ):
        raise ValueError("Data Quality execution capacity is exhausted.")

    return installation, source
