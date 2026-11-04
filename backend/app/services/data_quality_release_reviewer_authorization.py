"""Internal Phase 5E release-evidence reviewer validation.

Validation only. Does not authenticate the caller, confirm evidence,
authorize capacity release, or commit. The caller owns the transaction.

The restrictive preliminary policy requires an active installation
administrator with explicit membership in the evidence project.
"""

from uuid import UUID

from sqlalchemy import select

from app.models.user import User
from app.models.project_access import ProjectAccess


def require_release_reviewer_authority(
    db,
    *,
    reviewer_user_id: UUID,
    project_id: UUID,
) -> None:
    """Check current reviewer status under caller-owned transaction."""
    if not isinstance(reviewer_user_id, UUID):
        raise ValueError("Invalid reviewer identity.")

    if not isinstance(project_id, UUID):
        raise ValueError("Invalid reviewer project identity.")

    reviewer = db.scalar(
        select(User)
        .where(
            User.id == reviewer_user_id,
            User.is_active.is_(True),
            User.is_installation_admin.is_(True),
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if reviewer is None:
        raise ValueError("Active installation administrator reviewer required.")

    membership = db.scalar(
        select(ProjectAccess.id)
        .where(
            ProjectAccess.user_id == reviewer_user_id,
            ProjectAccess.project_id == project_id,
        )
        .with_for_update()
    )

    if membership is None:
        raise ValueError("Reviewer project membership required.")
