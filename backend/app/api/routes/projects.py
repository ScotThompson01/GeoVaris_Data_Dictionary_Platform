import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.db.session import get_db
from app.models.client import Client
from app.models.project import Project
from app.models.project_access import ProjectAccess
from app.schemas.project import ProjectCreate, ProjectRead
from app.schemas.project_settings import (
    ProjectSettingsRead,
    ProjectSettingsUpdate,
)
from app.services.project_administration import (
    require_project_administrator,
    update_steward_self_approval,
)
from app.services.project_authorization import require_project_access

router = APIRouter()


@router.get("", response_model=list[ProjectRead])
def list_projects(
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    query = (
        select(Project)
        .join(ProjectAccess, ProjectAccess.project_id == Project.id)
        .where(ProjectAccess.user_id == session.user.id)
        .order_by(Project.name)
    )
    return db.scalars(query).all()


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    # Project provisioning is disabled until an explicit permission
    # and provisioning workflow is implemented.
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Project creation is not permitted.",
    )


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    require_project_access(
        db,
        user_id=session.user.id,
        project_id=project_id,
    )
    return project


@router.get("/{project_id}/settings", response_model=ProjectSettingsRead)
def get_project_settings(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    """Read project settings only when the user has explicit project access."""
    require_project_access(
        db,
        user_id=session.user.id,
        project_id=project_id,
    )

    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    return ProjectSettingsRead(
        project_id=project.id,
        allow_steward_self_approval=project.allow_steward_self_approval,
    )


@router.patch("/{project_id}/settings", response_model=ProjectSettingsRead)
def update_project_settings(
    project_id: uuid.UUID,
    payload: ProjectSettingsUpdate,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    """Change a project setting with authorization and audit history."""
    require_project_access(
        db,
        user_id=session.user.id,
        project_id=project_id,
    )
    require_project_administrator(session.user)

    project = db.scalar(select(Project).where(Project.id == project_id).with_for_update())
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    update_steward_self_approval(
        db,
        project=project,
        actor_user_id=session.user.id,
        enabled=payload.allow_steward_self_approval,
    )

    return ProjectSettingsRead(
        project_id=project.id,
        allow_steward_self_approval=project.allow_steward_self_approval,
    )
