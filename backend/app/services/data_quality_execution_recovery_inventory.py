"""Read-only inventory of protected Phase 5E workloads.

Internal-only service. NOT connected to API routes or runtime recovery.

The caller must independently establish project authorization.
An active workload is not evidence of an interruption or source shutdown.

This service never updates execution state, releases reservations,
commits transactions, or contacts client data sources.
"""

from uuid import UUID

from sqlalchemy import select

from app.models.data_quality_workload_ownership import (
    DataQualityWorkloadOwnership,
)


PROTECTED_OWNERSHIP_STATES = ("reserved", "unresolved")


def list_project_protected_workload_candidates(
    db,
    *,
    project_id: UUID,
) -> list[DataQualityWorkloadOwnership]:
    """List protected workloads for an already-authorized project.

    Include all active ownership records regardless of execution status.
    The results are candidates for monitoring, not confirmed failures.
    """
    if not isinstance(project_id, UUID):
        raise ValueError("Invalid project identity.")

    statement = (
        select(DataQualityWorkloadOwnership)
        .where(
            DataQualityWorkloadOwnership.project_id == project_id,
            DataQualityWorkloadOwnership.ownership_state.in_(
                PROTECTED_OWNERSHIP_STATES
            ),
        )
        .order_by(
            DataQualityWorkloadOwnership.created_at,
            DataQualityWorkloadOwnership.id,
        )
    )

    return list(db.scalars(statement).all())
