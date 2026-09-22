"""Reusable checks for explicit data-source access."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.data_source import DataSource
from app.services.project_authorization import require_project_access


def require_data_source_access(
    db: Session,
    *,
    user_id: uuid.UUID,
    data_source_id: uuid.UUID,
) -> DataSource:
    """Return the source only when its project has an explicit user grant."""
    data_source = db.get(DataSource, data_source_id)

    if data_source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found.",
        )

    try:
        require_project_access(
            db,
            user_id=user_id,
            project_id=data_source.project_id,
        )
    except HTTPException as exc:
        if exc.status_code != status.HTTP_404_NOT_FOUND:
            raise
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found.",
        ) from None

    return data_source
