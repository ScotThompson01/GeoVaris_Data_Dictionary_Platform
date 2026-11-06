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
from app.services.data_quality_persisted_release_validation import (
    validate_persisted_admin_resolution_under_locks,
)
from app.services.data_quality_release_reviewer_authorization import (
    require_release_reviewer_authority,
)
from app.services.data_quality_execution_release_policy import (
    ReleaseEvidenceType,
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
    """Disabled legacy entry point; never releases capacity.

    Caller-supplied authorization flags and callbacks are not trusted
    release evidence. Retained solely to reject legacy invocations.
    """
    raise ValueError(
        "Legacy release authorization disabled; "
        "trusted persisted authorization is required."
    )


def stage_locked_persisted_admin_release(
    db,
    *,
    project_id: UUID,
    ownership_id: UUID,
    data_source_id: UUID,
    evidence_id: UUID,
    trusted_actor_user_id: UUID,
    reason: str,
    evidence_reference: str,
) -> None:
    """Stage administrator release after live persisted authorization.

    Internal only; not connected to runtime. The caller must establish
    authenticated actor identity independently. The caller also owns
    commit and rollback.

    Source-termination releases are intentionally unsupported.
    """
    for name, value in (
        ("project_id", project_id),
        ("ownership_id", ownership_id),
        ("data_source_id", data_source_id),
        ("evidence_id", evidence_id),
        ("trusted_actor_user_id", trusted_actor_user_id),
    ):
        if not isinstance(value, UUID):
            raise ValueError(f"Invalid {name}.")

    for name, value, limit in (
        ("reason", reason, 1000),
        ("evidence_reference", evidence_reference, 1000),
    ):
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > limit
        ):
            raise ValueError(f"Invalid release {name}.")

    actor = str(trusted_actor_user_id)

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

    # Authorization is compulsory and lives inside this transaction.
    # Never substitute a caller-provided callback or Boolean.
    evidence = validate_persisted_admin_resolution_under_locks(
        db,
        ownership,
        evidence_id=evidence_id,
        trusted_actor_user_id=trusted_actor_user_id,
    )

    require_release_reviewer_authority(
        db,
        reviewer_user_id=evidence.verified_by_user_id,
        project_id=project_id,
    )

    if (
        evidence.reason.strip() != reason.strip()
        or evidence.evidence_reference.strip()
        != evidence_reference.strip()
    ):
        raise ValueError(
            "Release audit details differ from persisted evidence."
        )

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