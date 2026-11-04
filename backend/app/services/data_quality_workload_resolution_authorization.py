"""Fail-closed project-scoped workload-resolution authorization.

This proposal is not connected to production execution or release.
Authorization does not establish source termination or release evidence.
"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from app.models.data_quality_workload_resolution_grant import (
    DataQualityWorkloadResolutionGrant,
)
from app.services.project_authorization import require_project_access


def require_workload_resolution_authority(
    db,
    *,
    user_id: UUID,
    project_id: UUID,
) -> None:
    """Require project access and an active dedicated resolution grant."""

    if not isinstance(user_id, UUID) or not isinstance(project_id, UUID):
        raise ValueError("Valid user and project identities are required.")

    require_project_access(
        db,
        user_id=user_id,
        project_id=project_id,
    )

    grant_id = db.scalar(
        select(DataQualityWorkloadResolutionGrant.id).where(
            DataQualityWorkloadResolutionGrant.user_id == user_id,
            DataQualityWorkloadResolutionGrant.project_id == project_id,
            DataQualityWorkloadResolutionGrant.revoked_at.is_(None),
        )
    )

    if grant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dedicated workload resolution permission required.",
        )
