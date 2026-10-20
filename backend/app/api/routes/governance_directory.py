"""Client-scoped Governance Directory endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.api.dependencies.admin import require_installation_admin
from app.db.session import get_db
from app.models.governance_assignment import GovernanceAssignment
from app.models.governance_department import GovernanceDepartment
from app.models.governance_person import GovernancePerson
from app.schemas.governance_assignment import GovernanceAssignmentCreate, GovernanceAssignmentRead
from app.schemas.governance_department import (
    GovernanceDepartmentCreate,
    GovernanceDepartmentRead,
)
from app.schemas.governance_person import GovernancePersonCreate, GovernancePersonRead
from app.services.client_authorization import require_client_access

router = APIRouter()


@router.get("/{client_id}/governance/people")
def list_governance_people(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    """List people only for a client explicitly granted to the user."""
    require_client_access(
        db,
        user_id=session.user.id,
        client_id=client_id,
    )

    people = db.scalars(
        select(GovernancePerson)
        .where(GovernancePerson.client_id == client_id)
        .order_by(GovernancePerson.full_name, GovernancePerson.id)
    ).all()

    return [
        {
            "id": person.id,
            "client_id": person.client_id,
            "full_name": person.full_name,
            "job_title": person.job_title,
            "business_email": person.business_email,
            "phone": person.phone,
            "contact_url": person.contact_url,
            "is_active": person.is_active,
        }
        for person in people
    ]

@router.get("/{client_id}/governance/departments")
def list_governance_departments(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    """List departments only for a client explicitly granted to the user."""
    require_client_access(
        db,
        user_id=session.user.id,
        client_id=client_id,
    )

    departments = db.scalars(
        select(GovernanceDepartment)
        .where(GovernanceDepartment.client_id == client_id)
        .order_by(GovernanceDepartment.name, GovernanceDepartment.id)
    ).all()

    return [
        {
            "id": department.id,
            "client_id": department.client_id,
            "name": department.name,
            "description": department.description,
            "is_active": department.is_active,
        }
        for department in departments
    ]

@router.get("/{client_id}/governance/assignments")
def list_governance_assignments(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    """List assignments only for a client explicitly granted to the user."""
    require_client_access(
        db,
        user_id=session.user.id,
        client_id=client_id,
    )

    assignments = db.scalars(
        select(GovernanceAssignment)
        .where(GovernanceAssignment.client_id == client_id)
        .order_by(
            GovernanceAssignment.department_id,
            GovernanceAssignment.role,
            GovernanceAssignment.id,
        )
    ).all()

    return [
        {
            "id": assignment.id,
            "client_id": assignment.client_id,
            "person_id": assignment.person_id,
            "department_id": assignment.department_id,
            "role": assignment.role,
            "effective_start": assignment.effective_start,
            "effective_end": assignment.effective_end,
            "is_active": assignment.is_active,
        }
        for assignment in assignments
    ]

@router.post(
    "/{client_id}/governance/departments",
    response_model=GovernanceDepartmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_governance_department(
    client_id: uuid.UUID,
    payload: GovernanceDepartmentCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_installation_admin),
):
    """Create a department for a client accessible to this administrator."""
    require_client_access(
        db,
        user_id=admin.id,
        client_id=client_id,
    )

    department = GovernanceDepartment(
        client_id=client_id,
        name=payload.name,
        description=payload.description,
    )

    db.add(department)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        diagnostic = getattr(exc.orig, "diag", None)
        constraint_name = getattr(diagnostic, "constraint_name", None)

        if constraint_name == "uq_governance_departments_client_name":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Department name already exists for this client.",
            ) from None

        raise

    db.refresh(department)
    return department




@router.post(
    "/{client_id}/governance/people",
    response_model=GovernancePersonRead,
    status_code=status.HTTP_201_CREATED,
)
def create_governance_person(
    client_id: uuid.UUID,
    payload: GovernancePersonCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_installation_admin),
):
    """Create a directory person for a client accessible to this administrator."""
    require_client_access(
        db,
        user_id=admin.id,
        client_id=client_id,
    )

    person = GovernancePerson(
        client_id=client_id,
        full_name=payload.full_name,
        job_title=payload.job_title,
        business_email=payload.business_email,
        phone=payload.phone,
        contact_url=payload.contact_url,
    )

    db.add(person)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    db.refresh(person)
    return person


@router.post(
    "/{client_id}/governance/assignments",
    response_model=GovernanceAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_governance_assignment(
    client_id: uuid.UUID,
    payload: GovernanceAssignmentCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_installation_admin),
):
    """Assign a client-owned person to a client-owned department."""
    require_client_access(
        db,
        user_id=admin.id,
        client_id=client_id,
    )

    person = db.scalar(
        select(GovernancePerson).where(
            GovernancePerson.id == payload.person_id,
            GovernancePerson.client_id == client_id,
        )
    )
    if person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found for this client.",
        )

    department = db.scalar(
        select(GovernanceDepartment).where(
            GovernanceDepartment.id == payload.department_id,
            GovernanceDepartment.client_id == client_id,
        )
    )
    if department is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found for this client.",
        )

    if not person.is_active or not department.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Person and department must both be active.",
        )

    assignment = GovernanceAssignment(
        client_id=client_id,
        person_id=payload.person_id,
        department_id=payload.department_id,
        role=payload.role,
        effective_start=payload.effective_start,
        effective_end=payload.effective_end,
    )

    db.add(assignment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    db.refresh(assignment)
    return assignment
