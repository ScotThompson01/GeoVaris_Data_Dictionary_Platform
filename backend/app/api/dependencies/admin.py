"""Authorization dependency for installation administrators."""

from fastapi import Depends, HTTPException, status

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.models.user import User


def require_installation_admin(
    authenticated: AuthenticatedSession = Depends(
        require_authenticated_session
    ),
) -> User:
    """Require an active, authenticated installation administrator."""
    user = authenticated.user

    if not user.is_active or not user.is_installation_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )

    return user
