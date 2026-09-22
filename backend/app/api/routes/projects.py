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
