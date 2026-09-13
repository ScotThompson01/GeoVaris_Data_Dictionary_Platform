import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.data_field import DataField
from app.models.field_governance_metadata import FieldGovernanceMetadata
from app.schemas.field_governance_metadata import (
    FieldGovernanceMetadataUpdate,
    FieldGovernanceMetadataView,
)

router = APIRouter()


def _get_governance_record(
    db: Session,
    data_field_id: uuid.UUID,
) -> FieldGovernanceMetadata | None:
    return db.scalar(
        select(FieldGovernanceMetadata).where(
            FieldGovernanceMetadata.data_field_id
            == data_field_id
        )
    )


@router.get(
    "/{data_field_id}",
    response_model=FieldGovernanceMetadataView,
)
def get_field_governance(
    data_field_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    data_field = db.get(
        DataField,
        data_field_id,
    )

    if data_field is None:
        raise HTTPException(
            status_code=404,
            detail="Data field not found.",
        )

    governance = _get_governance_record(
        db,
        data_field_id,
    )

    if governance is None:
        return FieldGovernanceMetadataView(
            data_field_id=data_field_id,
            is_cde=False,
            approval_status="draft",
        )

    return governance


@router.put(
    "/{data_field_id}",
    response_model=FieldGovernanceMetadataView,
)
def save_field_governance(
    data_field_id: uuid.UUID,
    payload: FieldGovernanceMetadataUpdate,
    db: Session = Depends(get_db),
):
    data_field = db.get(
        DataField,
        data_field_id,
    )

    if data_field is None:
        raise HTTPException(
            status_code=404,
            detail="Data field not found.",
        )

    governance = _get_governance_record(
        db,
        data_field_id,
    )

    if governance is None:
        governance = FieldGovernanceMetadata(
            data_field_id=data_field_id,
            is_cde=False,
            approval_status="draft",
        )

        db.add(governance)

    update_values = payload.model_dump(
        exclude_unset=True,
    )

    for field_name, value in update_values.items():
        # These columns are non-nullable in the database.
        if field_name == "is_cde" and value is None:
            continue

        if field_name == "approval_status" and value is None:
            continue

        setattr(
            governance,
            field_name,
            value,
        )

    db.commit()
    db.refresh(governance)

    return governance