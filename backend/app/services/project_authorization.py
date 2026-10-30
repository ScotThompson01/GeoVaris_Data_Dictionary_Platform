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


def require_dq_rule_approver(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    """Require explicit project membership and Data Quality approval authority."""
    require_project_access(
        db,
        user_id=user_id,
        project_id=project_id,
    )

    approval_grant_id = db.scalar(
        select(ProjectAccess.id).where(
            ProjectAccess.user_id == user_id,
            ProjectAccess.project_id == project_id,
            ProjectAccess.can_approve_dq_rules.is_(True),
        )
    )

    if approval_grant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Data Quality rule approval permission required.",
        )


def require_dq_rule_executor(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    """Require project membership and explicit Data Quality execution permission."""
    require_project_access(
        db,
        user_id=user_id,
        project_id=project_id,
    )

    execution_grant_id = db.scalar(
        select(ProjectAccess.id).where(
            ProjectAccess.user_id == user_id,
            ProjectAccess.project_id == project_id,
            ProjectAccess.can_execute_dq_rules.is_(True),
        )
    )

    if execution_grant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Data Quality rule execution permission required.",
        )


def require_data_source_connection_manager(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    """Require explicit project membership and connection-management permission."""
    require_project_access(
        db,
        user_id=user_id,
        project_id=project_id,
    )

    management_grant_id = db.scalar(
        select(ProjectAccess.id).where(
            ProjectAccess.user_id == user_id,
            ProjectAccess.project_id == project_id,
            ProjectAccess.can_manage_data_source_connections.is_(True),
        )
    )

    if management_grant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Data source connection management permission required.",
        )


