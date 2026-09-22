import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.db.session import get_db
from app.models.data_source import DataSource
from app.models.project_access import ProjectAccess
from app.models.scan import Scan
from app.schemas.scan import ScanCreate, ScanRead
from app.services.data_source_authorization import require_data_source_access

router = APIRouter()


@router.get("", response_model=list[ScanRead])
def list_scans(
    data_source_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    statement = (
        select(Scan)
        .join(DataSource, DataSource.id == Scan.data_source_id)
        .join(
            ProjectAccess,
            ProjectAccess.project_id == DataSource.project_id,
        )
        .where(ProjectAccess.user_id == session.user.id)
    )

    if data_source_id is not None:
        statement = statement.where(
            Scan.data_source_id == data_source_id
        )

    statement = statement.order_by(
        Scan.created_at.desc()
    )

    return db.scalars(statement).all()


@router.post(
    "",
    response_model=ScanRead,
    status_code=status.HTTP_201_CREATED,
)
def create_scan(
    payload: ScanCreate,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    require_data_source_access(
        db,
        user_id=session.user.id,
        data_source_id=payload.data_source_id,
    )

    scan = Scan(
        data_source_id=payload.data_source_id,
        scan_type=payload.scan_type,
        status=payload.status,
        connector_version=payload.connector_version,
    )

    db.add(scan)
    db.commit()
    db.refresh(scan)

    return scan


@router.get(
    "/{scan_id}",
    response_model=ScanRead,
)
def get_scan(
    scan_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    scan = db.get(
        Scan,
        scan_id,
    )

    if scan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found.",
        )

    try:
        require_data_source_access(
            db,
            user_id=session.user.id,
            data_source_id=scan.data_source_id,
        )
    except HTTPException as exc:
        if exc.status_code != status.HTTP_404_NOT_FOUND:
            raise
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found.",
        ) from None

    return scan