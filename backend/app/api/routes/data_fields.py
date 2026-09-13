import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.data_field import DataField
from app.models.source_object import SourceObject
from app.schemas.data_field import DataFieldCreate, DataFieldRead

router = APIRouter()


@router.get("", response_model=list[DataFieldRead])
def list_data_fields(
    source_object_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    statement = select(DataField)

    if source_object_id is not None:
        statement = statement.where(
            DataField.source_object_id == source_object_id
        )

    statement = statement.order_by(
        DataField.ordinal_position,
        DataField.field_name,
    )

    return db.scalars(statement).all()


@router.post(
    "",
    response_model=DataFieldRead,
    status_code=status.HTTP_201_CREATED,
)
def create_data_field(
    payload: DataFieldCreate,
    db: Session = Depends(get_db),
):
    source_object = db.get(
        SourceObject,
        payload.source_object_id,
    )

    if source_object is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source object not found.",
        )

    data_field = DataField(
        source_object_id=payload.source_object_id,
        field_name=payload.field_name.strip(),
        ordinal_position=payload.ordinal_position,
        native_data_type=payload.native_data_type,
        normalized_data_type=payload.normalized_data_type,
        max_length=payload.max_length,
        numeric_precision=payload.numeric_precision,
        numeric_scale=payload.numeric_scale,
        is_nullable=payload.is_nullable,
        is_primary_key=payload.is_primary_key,
        is_unique=payload.is_unique,
        default_value=payload.default_value,
        source_comment=payload.source_comment,
    )

    db.add(data_field)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A field with this name already exists for the source object.",
        )

    db.refresh(data_field)

    return data_field


@router.get(
    "/{data_field_id}",
    response_model=DataFieldRead,
)
def get_data_field(
    data_field_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    data_field = db.get(
        DataField,
        data_field_id,
    )

    if data_field is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data field not found.",
        )

    return data_field