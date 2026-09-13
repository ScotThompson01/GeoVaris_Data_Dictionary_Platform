import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.profiling_result import ProfilingResult
from app.schemas.profiling_result import ProfilingResultRead

router = APIRouter()


@router.get(
    "",
    response_model=list[ProfilingResultRead],
)
def list_profiling_results(
    scan_id: uuid.UUID | None = Query(default=None),
    data_field_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    statement = select(ProfilingResult)

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

    return result