"""Authentication dependencies for protected API endpoints."""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.services.auth_sessions import get_session_user


@dataclass(frozen=True)
class AuthenticatedSession:
    user: User
    token: str


def require_authenticated_session(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthenticatedSession:
    """Validate the bearer token supplied by the Next.js server."""
    authorization = request.headers.get("Authorization", "")
    scheme, separator, token = authorization.partition(" ")

    if (
        not separator
        or scheme.lower() != "bearer"
        or not token
        or token.strip() != token
        or " " in token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_session_user(db, token)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedSession(user=user, token=token)