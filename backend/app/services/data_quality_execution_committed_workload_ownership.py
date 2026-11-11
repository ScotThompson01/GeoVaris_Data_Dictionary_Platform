"""Independently verify committed workload ownership without modifying it.

This service is not a runtime execution authorization or a capacity-release
mechanism. An uncertain database read never becomes successful verification.
"""

from uuid import UUID

from sqlalchemy import select

from app.models.data_quality_workload_ownership import (
    DataQualityWorkloadOwnership,
)


class CommittedWorkloadOwnershipUnavailableError(RuntimeError):
    """The exact reserved, unreleased workload ownership was not verified."""


def verify_committed_workload_ownership(
    *,
    session_factory,
    execution_id: UUID,
    project_id: UUID,
    data_source_id: UUID,
) -> UUID:
    """Verify current committed ownership in an independently opened session.

    The caller must separately verify committed connection authorization for
    the same identities and approved connection revision. This function
    neither starts execution nor performs client-source measurements.
    """
    if not callable(session_factory):
        raise ValueError("A session factory is required.")

    if not all(
        isinstance(value, UUID)
        for value in (execution_id, project_id, data_source_id)
    ):
        raise ValueError("Valid ownership UUID identities are required.")

    db = session_factory()

    try:
        ownership = db.scalar(
            select(DataQualityWorkloadOwnership).where(
                DataQualityWorkloadOwnership.execution_id == execution_id
            )
        )

        if ownership is None:
            raise CommittedWorkloadOwnershipUnavailableError(
                "Committed workload ownership is unavailable."
            )

        if (
            ownership.execution_id != execution_id
            or ownership.project_id != project_id
            or ownership.data_source_id != data_source_id
        ):
            raise CommittedWorkloadOwnershipUnavailableError(
                "Committed workload ownership identity mismatch."
            )

        if ownership.ownership_state != "RESERVED":
            raise CommittedWorkloadOwnershipUnavailableError(
                "Committed workload ownership is not reserved."
            )

        if any(
            value is not None
            for value in (
                ownership.released_at,
                ownership.release_actor,
                ownership.release_reason,
                ownership.release_evidence_reference,
            )
        ):
            raise CommittedWorkloadOwnershipUnavailableError(
                "Committed workload ownership has release metadata."
            )

        return execution_id
    finally:
        db.close()