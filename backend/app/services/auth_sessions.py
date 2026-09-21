"""Create, validate, and revoke database-backed authentication sessions."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth_session import AuthSession
from app.models.user import User


SESSION_LIFETIME = timedelta(hours=8)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_auth_session(db: Session, user: User) -> str:
    """Create a session and return its bearer token exactly once."""
    if not user.is_active:
        raise ValueError("Cannot create a session for an inactive user.")

    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=_token_hash(token),
            expires_at=now + SESSION_LIFETIME,
        )
    )
    db.commit()

    return token


def get_session_user(db: Session, token: str | None) -> User | None:
    """Return the active user for a valid, unexpired session."""
    if not token:
        return None

    now = datetime.now(timezone.utc)

    statement = (
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            AuthSession.token_hash == _token_hash(token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
            User.is_active.is_(True),
        )
    )

    return db.scalar(statement)


def revoke_auth_session(db: Session, token: str | None) -> None:
    """Revoke a session if it exists; otherwise do nothing."""
    if not token:
        return

    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == _token_hash(token),
            AuthSession.revoked_at.is_(None),
        )
    )

    if session is None:
        return

    session.revoked_at = datetime.now(timezone.utc)
    db.commit()