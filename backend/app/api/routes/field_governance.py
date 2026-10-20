import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.db.session import get_db
from app.models.data_field import DataField
from app.models.project import Project
from app.models.governance_assignment import GovernanceAssignment
from app.models.governance_person import GovernancePerson
from app.models.governance_department import GovernanceDepartment
from app.models.data_source import DataSource
from app.models.source_object import SourceObject
from app.services.project_authorization import require_project_access
from app.models.field_governance_metadata import FieldGovernanceMetadata
from app.schemas.field_governance_metadata import (
    FieldGovernanceMetadataUpdate,
    FieldGovernanceMetadataView,
)

router = APIRouter()


def _validate_steward_assignment(
    db: Session,
    assignment_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Data field project not found.",
        )

    assignment = db.scalar(
        select(GovernanceAssignment).where(
            GovernanceAssignment.id == assignment_id,
            GovernanceAssignment.client_id == project.client_id,
        )
    )

    if assignment is None:
        raise HTTPException(
            status_code=422,
            detail="Steward assignment is not available for this client.",
        )

    today = date.today()

    if (
        assignment.role != "data_steward"
        or not assignment.is_active
        or (
            assignment.effective_start is not None
            and assignment.effective_start > today
        )
        or (
            assignment.effective_end is not None
            and assignment.effective_end < today
        )
    ):
        raise HTTPException(
            status_code=422,
            detail="Steward assignment is not currently valid.",
        )

    person = db.scalar(
        select(GovernancePerson).where(
            GovernancePerson.id == assignment.person_id,
            GovernancePerson.client_id == project.client_id,
        )
    )
    department = db.scalar(
        select(GovernanceDepartment).where(
            GovernanceDepartment.id == assignment.department_id,
            GovernanceDepartment.client_id == project.client_id,
        )
    )

    if (
        person is None
        or department is None
        or not person.is_active
        or not department.is_active
    ):
        raise HTTPException(
            status_code=422,
            detail="Steward person and department must be active.",
        )


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

    if update_values.get("steward_assignment_id") is not None:
        _validate_steward_assignment(
            db,
            update_values["steward_assignment_id"],
            data_source.project_id,
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