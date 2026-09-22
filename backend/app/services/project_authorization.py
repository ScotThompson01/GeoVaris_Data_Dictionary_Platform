"""Reusable checks for explicit project access."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project_access import ProjectAccess


def require_project_access(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    """Raise 404 unless the user has an explicit grant for this project."""
    grant_id = db.scalar(
        select(ProjectAccess.id).where(
            ProjectAccess.user_id == user_id,
            ProjectAccess.project_id == project_id,
        )
    )

    if grant_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
