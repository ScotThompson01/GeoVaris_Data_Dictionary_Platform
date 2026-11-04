"""Internal-only Phase 5E persisted administrator release staging.

Not runtime-connected or production-authorized. The caller must
independently authenticate the actor and establish reviewer authority.
Confirmed database evidence is not, by itself, proof of authority.

The underlying transaction acquires capacity controls, ownership,
and reservations before this service validates persisted evidence.
The caller owns commit and rollback.
"""

from uuid import UUID

from app.services.data_quality_execution_release_policy import (
    ReleaseEvidenceType,
)
from app.services.data_quality_execution_release_transaction import (
    stage_verified_workload_release,
)
from app.services.data_quality_persisted_release_validation import (
    validate_persisted_admin_resolution_under_locks,
)


def stage_persisted_admin_resolution(
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
    """Stage a release only when scoped persisted evidence agrees.

    This function is an internal integration boundary, not an API.
    A future production entry point must independently establish
    actor and reviewer authority before invoking this function.
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

    for name, value in (
        ("reason", reason),
        ("evidence_reference", evidence_reference),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Release {name} is required.")

    def validate_after_locks(session, locked_ownership):
        evidence = validate_persisted_admin_resolution_under_locks(
            session,
            locked_ownership,
            evidence_id=evidence_id,
            trusted_actor_user_id=trusted_actor_user_id,
        )

        if (
            locked_ownership.project_id != project_id
            or locked_ownership.data_source_id != data_source_id
            or locked_ownership.id != ownership_id
        ):
            raise ValueError("Locked workload identity mismatch.")

        if (
            evidence.reason.strip() != reason.strip()
            or evidence.evidence_reference.strip()
            != evidence_reference.strip()
        ):
            raise ValueError(
                "Release audit details differ from persisted evidence."
            )

    stage_verified_workload_release(
        db,
        project_id=project_id,
        ownership_id=ownership_id,
        data_source_id=data_source_id,
        evidence_type=ReleaseEvidenceType.AUTHORIZED_ADMIN_RESOLUTION,
        actor=str(trusted_actor_user_id),
        reason=reason,
        evidence_reference=evidence_reference,
        source_termination_verified=False,
        administrator_authorized=True,
        validate_under_locks=validate_after_locks,
    )
