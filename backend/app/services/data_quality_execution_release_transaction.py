"""Internal transactional release staging for Phase 5E.

Not connected to runtime routes. The caller must independently establish
trusted source-termination verification or authorized administrator resolution.

The caller owns commit/rollback. No client-source I/O is performed.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.models.data_quality_execution_capacity_control import (
    DataQualityExecutionCapacityControl as CapacityControl,
)
from app.models.data_quality_execution_capacity_reservation import (
    DataQualityExecutionCapacityReservation as Reservation,
)
from app.models.data_quality_workload_ownership import (
    DataQualityWorkloadOwnership as Ownership,
)
from app.services.data_quality_execution_release_integrity import (
    validate_protected_workload,
)
from app.services.data_quality_execution_release_policy import (
    ReleaseEvidenceType,
    validate_release_evidence,
)


def stage_verified_workload_release(
    db,
    *,
    project_id: UUID,
    ownership_id: UUID,
    data_source_id: UUID,
    evidence_type: ReleaseEvidenceType,
    actor: str,
    reason: str,
    evidence_reference: str,
    source_termination_verified: bool = False,
    administrator_authorized: bool = False,
    validate_under_locks=None,
) -> None:
    """Stage release of ownership and both reservations atomically.

    Evidence flags MUST come from a trusted internal workflow, never
    directly from client/API request data. Not production-authorized.
    All cooperating admission/release writers must use identical
    lock ordering and PostgreSQL READ COMMITTED isolation.
    """

    for name, value in (
        ("project_id", project_id),
        ("ownership_id", ownership_id),
        ("data_source_id", data_source_id),
    ):
        if not isinstance(value, UUID):
            raise ValueError(f"Invalid {name}.")

    validate_release_evidence(
        evidence_type=evidence_type,
        actor=actor,
        reason=reason,
        evidence_reference=evidence_reference,
        source_termination_verified=source_termination_verified,
        administrator_authorized=administrator_authorized,
    )

    for name, value, limit in (
        ("actor", actor, 255),
        ("reason", reason, 1000),
        ("evidence_reference", evidence_reference, 1000),
    ):
        if len(value) > limit:
            raise ValueError(f"Release {name} exceeds the storage limit.")

    # Fixed locking order across cooperating writers:
    # installation control -> source control -> ownership -> reservations.
    installation = db.scalar(
        select(CapacityControl)
        .where(CapacityControl.scope_type == "installation")
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if installation is None or installation.data_source_id is not None:
        raise ValueError("Installation capacity control is unavailable.")

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
    ):
        raise ValueError("Source capacity control is unavailable.")

    ownership = db.scalar(
        select(Ownership)
        .where(
            Ownership.id == ownership_id,
            Ownership.project_id == project_id,
            Ownership.data_source_id == data_source_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if ownership is None:
        raise ValueError("Workload ownership was not found.")

    reservations = list(
        db.scalars(
            select(Reservation)
            .where(Reservation.ownership_id == ownership_id)
            .order_by(Reservation.reservation_scope, Reservation.id)
            .execution_options(populate_existing=True)
            .with_for_update()
        ).all()
    )

    validate_protected_workload(
        ownership=ownership,
        reservations=reservations,
    )

    by_scope = {
        reservation.reservation_scope: reservation
        for reservation in reservations
    }

    if (
        by_scope["installation"].capacity_control_id != installation.id
        or by_scope["source"].capacity_control_id != source.id
    ):
        raise ValueError("Reservations reference incorrect capacity controls.")

    # Additional internal checks must run after capacity and workload
    # locks, but before any ownership or reservation state is changed.
    # This callback never grants authorization by itself.
    if validate_under_locks is not None:
        if not callable(validate_under_locks):
            raise ValueError("Invalid locked release validator.")
        validate_under_locks(db, ownership)

    released_at = datetime.now(timezone.utc)

    for record, state_field in (
        (ownership, "ownership_state"),
        (by_scope["installation"], "reservation_state"),
        (by_scope["source"], "reservation_state"),
    ):
        setattr(record, state_field, "released")
        record.released_at = released_at
        record.release_actor = actor.strip()
        record.release_reason = reason.strip()
        record.release_evidence_reference = evidence_reference.strip()

    db.flush()