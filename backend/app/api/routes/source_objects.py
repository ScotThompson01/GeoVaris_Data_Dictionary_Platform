import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.data_source import DataSource
from app.models.source_object import SourceObject
from app.schemas.source_object import SourceObjectCreate, SourceObjectRead

router = APIRouter()


@router.get("", response_model=list[SourceObjectRead])
def list_source_objects(
    data_source_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    statement = select(SourceObject)

    if data_source_id is not None:
        statement = statement.where(
            SourceObject.data_source_id == data_source_id
        )

    statement = statement.order_by(SourceObject.object_name)

    return db.scalars(statement).all()


@router.post(
    "",
    response_model=SourceObjectRead,
    status_code=status.HTTP_201_CREATED,
)
def create_source_object(
    payload: SourceObjectCreate,
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

    source_object = SourceObject(
        data_source_id=payload.data_source_id,
        object_type=payload.object_type,
        object_name=payload.object_name.strip(),
        schema_name=payload.schema_name,
        native_name=payload.native_name,
        description=payload.description,
        row_count=payload.row_count,
    )

    db.add(source_object)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A source object with this name already exists for the data source.",
        )

    db.refresh(source_object)
    return source_object


@router.get(
    "/{source_object_id}",
    response_model=SourceObjectRead,
)
def get_source_object(
    source_object_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    source_object = db.get(
        SourceObject,
        source_object_id,
    )

    if source_object is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source object not found.",
        )

    return source_object