import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
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
from app.models.profiling_result import ProfilingResult
from app.schemas.profiling_result import ProfilingResultRead
from app.services.data_source_authorization import require_data_source_access

router = APIRouter()


@router.get(
    "",
    response_model=list[ProfilingResultRead],
)
def list_profiling_results(
    scan_id: uuid.UUID | None = Query(default=None),
    data_field_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    statement = (
        select(ProfilingResult)
        .join(Scan, Scan.id == ProfilingResult.scan_id)
        .join(DataSource, DataSource.id == Scan.data_source_id)
        .join(
            ProjectAccess,
            ProjectAccess.project_id == DataSource.project_id,
        )
        .where(ProjectAccess.user_id == session.user.id)
    )

    if scan_id is not None:
        statement = statement.where(
            ProfilingResult.scan_id == scan_id
        )

    if data_field_id is not None:
        statement = statement.where(
            ProfilingResult.data_field_id == data_field_id
        )

    statement = statement.order_by(
        ProfilingResult.created_at.desc()
    )

    return db.scalars(statement).all()


@router.get(
    "/{profiling_result_id}",
    response_model=ProfilingResultRead,
)
def get_profiling_result(
    profiling_result_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    result = db.get(
        ProfilingResult,
        profiling_result_id,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Profiling result not found.",
        )

    scan = db.get(Scan, result.scan_id)
    if scan is None:
        raise HTTPException(
            status_code=404,
            detail="Profiling result not found.",
        )

    try:
        require_data_source_access(
            db,
            user_id=session.user.id,
            data_source_id=scan.data_source_id,
        )
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        raise HTTPException(
            status_code=404,
            detail="Profiling result not found.",
        ) from None

    return result