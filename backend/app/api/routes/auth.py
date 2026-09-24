
"""Backend authentication endpoints for the Next.js server."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.core.passwords import verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    CurrentUserResponse,
    SignInRequest,
    SignInResponse,
)
from app.services.auth_sessions import (
    create_auth_session,
    revoke_auth_session,
)

router = APIRouter()


@router.post("/sign-in", response_model=SignInResponse)
def sign_in(
    payload: SignInRequest,
    db: Session = Depends(get_db),
) -> SignInResponse:
    """Verify local credentials and create an authentication session."""
    user = db.scalar(
        select(User).where(User.username == payload.username.strip())
    )

    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    token = create_auth_session(db, user)

    return SignInResponse(
        session_token=token,
        user_id=user.id,
        username=user.username,
    )


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user(
    authenticated: AuthenticatedSession = Depends(
        require_authenticated_session
    ),
) -> CurrentUserResponse:
    """Return the user associated with a valid authentication session."""
    return CurrentUserResponse(
        user_id=authenticated.user.id,
        username=authenticated.user.username,
        is_installation_admin=authenticated.user.is_installation_admin,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    authenticated: AuthenticatedSession = Depends(
        require_authenticated_session
    ),
    db: Session = Depends(get_db),
) -> None:
    """Revoke the session used to authenticate this request."""
    revoke_auth_session(db, authenticated.token)