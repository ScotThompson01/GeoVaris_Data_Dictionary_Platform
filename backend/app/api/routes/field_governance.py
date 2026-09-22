import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.db.session import get_db
from app.models.data_field import DataField
from app.models.data_source import DataSource
from app.models.source_object import SourceObject
from app.services.project_authorization import require_project_access
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
    session: AuthenticatedSession = Depends(require_authenticated_session),
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

    source_object = db.get(SourceObject, data_field.source_object_id)
    if source_object is None:
        raise HTTPException(
            status_code=404,
            detail="Data field not found.",
        )

    data_source = db.get(DataSource, source_object.data_source_id)
    if data_source is None:
        raise HTTPException(
            status_code=404,
            detail="Data field not found.",
        )

    try:
        require_project_access(
            db,
            user_id=session.user.id,
            project_id=data_source.project_id,
        )
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        raise HTTPException(
            status_code=404,
            detail="Data field not found.",
        ) from exc

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
    session: AuthenticatedSession = Depends(require_authenticated_session),
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

    source_object = db.get(SourceObject, data_field.source_object_id)
    if source_object is None:
        raise HTTPException(
            status_code=404,
            detail="Data field not found.",
        )

    data_source = db.get(DataSource, source_object.data_source_id)
    if data_source is None:
        raise HTTPException(
            status_code=404,
            detail="Data field not found.",
        )

    try:
        require_project_access(
            db,
            user_id=session.user.id,
            project_id=data_source.project_id,
        )
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        raise HTTPException(
            status_code=404,
            detail="Data field not found.",
        ) from exc

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