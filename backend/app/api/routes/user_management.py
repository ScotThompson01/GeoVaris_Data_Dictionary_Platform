"""Installation administrator endpoints for user management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_installation_admin
from app.core.passwords import hash_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user_management import (
    CreateManagedUserRequest,
    UpdateManagedUserRoleRequest,
    ManagedUserResponse,
)

router = APIRouter(dependencies=[Depends(require_installation_admin)])


def user_response(user: User) -> ManagedUserResponse:
    return ManagedUserResponse(
        user_id=user.id,
        username=user.username,
        is_active=user.is_active,
        is_installation_admin=user.is_installation_admin,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("", response_model=list[ManagedUserResponse])
def list_users(
    db: Session = Depends(get_db),
) -> list[ManagedUserResponse]:
    """List local users for installation administrators only."""
    users = db.scalars(
        select(User).order_by(User.username, User.id)
    ).all()

    return [user_response(user) for user in users]


@router.post(
    "",
    response_model=ManagedUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: CreateManagedUserRequest,
    db: Session = Depends(get_db),
) -> ManagedUserResponse:
    """Create an active standard user without administrator privileges."""
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        is_active=True,
        is_installation_admin=False,
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already in use.",
        ) from None

    return user_response(user)


@router.patch(
    "/{user_id}/role",
    response_model=ManagedUserResponse,
)
def update_user_role(
    user_id: UUID,
    payload: UpdateManagedUserRoleRequest,
    db: Session = Depends(get_db),
    administrator: User = Depends(require_installation_admin),
) -> ManagedUserResponse:
    """Change another user's installation role."""
    target = db.get(User, user_id)

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if (
        target.id == administrator.id
        and not payload.is_installation_admin
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot remove your own Administrator role.",
        )

    target.is_installation_admin = payload.is_installation_admin
    db.commit()
    db.refresh(target)

    return user_response(target)
