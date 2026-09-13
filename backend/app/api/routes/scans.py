import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.data_source import DataSource
from app.models.scan import Scan
from app.schemas.scan import ScanCreate, ScanRead

router = APIRouter()


@router.get("", response_model=list[ScanRead])
def list_scans(
    data_source_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    statement = select(Scan)

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
):
    data_source = db.get(
        DataSource,
        payload.data_source_id,
    )

    if data_source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found.",
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

    return scan