"""Internal validation of persisted administrator release evidence.

Validation only: does not authenticate callers, establish reviewer
authority, prove source termination, release capacity, or commit.

Must be called inside a caller-owned transaction after capacity-control,
ownership, and reservation locks have been acquired in that order.
"""

from uuid import UUID

from app.services.data_quality_execution_release_policy import (
    ReleaseEvidenceType,
)
from app.services.data_quality_workload_release_evidence_lookup import (
    load_consistent_release_evidence,
)


def validate_persisted_admin_resolution_under_locks(
    db,
    locked_ownership,
    *,
    evidence_id: UUID,
    trusted_actor_user_id: UUID,
):
    """Return consistent evidence; never grant release permission itself."""
    if not isinstance(evidence_id, UUID):
        raise ValueError("Invalid persisted evidence identity.")

    if not isinstance(trusted_actor_user_id, UUID):
        raise ValueError("Invalid trusted actor identity.")

    if locked_ownership is None:
        raise ValueError("Locked workload ownership is required.")

    for name in ("id", "project_id", "data_source_id"):
        if not isinstance(getattr(locked_ownership, name, None), UUID):
            raise ValueError(f"Invalid locked workload {name}.")

    if getattr(locked_ownership, "ownership_state", None) not in (
        "reserved",
        "unresolved",
    ):
        raise ValueError("Workload is not protected.")

    evidence = load_consistent_release_evidence(
        db,
        evidence_id=evidence_id,
        ownership_id=locked_ownership.id,
        project_id=locked_ownership.project_id,
        data_source_id=locked_ownership.data_source_id,
    )

    if (
        evidence.evidence_type
        != ReleaseEvidenceType.AUTHORIZED_ADMIN_RESOLUTION.value
    ):
        raise ValueError(
            "Administrator resolution evidence is required for this path."
        )

    if evidence.actor_user_id != trusted_actor_user_id:
        raise ValueError("Trusted actor does not match release evidence.")

    return evidence
