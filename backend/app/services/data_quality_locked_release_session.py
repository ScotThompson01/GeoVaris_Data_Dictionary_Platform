"""Locked session revalidation for internal Phase 5E releases.

Not connected to runtime and not production-authorized.

Call only after the release transaction has acquired its capacity,
ownership, reservation, evidence, actor, and reviewer locks.

The caller owns commit/rollback. No token is logged or persisted here.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.models.auth_session import AuthSession
from app.services.auth_sessions import _token_hash


def require_locked_release_session(
    db,
    *,
    session_token: str,
    expected_actor_user_id: UUID,
) -> None:
    """Require a live session belonging to the authorized release actor.

    PostgreSQL READ COMMITTED and the row lock coordinate this check
    with a concurrent session revocation. The transaction must retain
    the lock until commit or rollback.
    """
    if (
        not isinstance(session_token, str)
        or not session_token
        or session_token.strip() != session_token
        or any(character.isspace() for character in session_token)
        or not isinstance(expected_actor_user_id, UUID)
    ):
        raise PermissionError("Valid authenticated release session required.")

    now = datetime.now(timezone.utc)

    record = db.scalar(
        select(AuthSession)
        .where(
            AuthSession.token_hash == _token_hash(session_token),
            AuthSession.user_id == expected_actor_user_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if (
        record is None
        or record.user_id != expected_actor_user_id
        or record.revoked_at is not None
        or record.expires_at <= datetime.now(timezone.utc)
    ):
        raise PermissionError("Valid authenticated release session required.")
