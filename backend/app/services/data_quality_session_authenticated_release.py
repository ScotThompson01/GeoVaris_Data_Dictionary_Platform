"""Internal session-authenticated administrator release staging.

Not connected to runtime routes or production-authorized.

The actor identity comes from the existing validated database-backed
session, never from an actor UUID supplied by the caller.

The caller owns transaction commit/rollback. No client-source I/O occurs.
"""

from uuid import UUID

from app.services.auth_sessions import get_session_user
from app.services.data_quality_persisted_admin_release_transaction import (
    stage_persisted_admin_resolution,
)


def stage_session_authenticated_admin_resolution(
    db,
    *,
    session_token: str,
    project_id: UUID,
    ownership_id: UUID,
    data_source_id: UUID,
    evidence_id: UUID,
    reason: str,
    evidence_reference: str,
) -> None:
    """Stage release using the authenticated session user's identity.

    Session validation establishes the actor identity. The underlying
    locked transaction independently validates persisted release
    evidence, actor authority, and reviewer authority.

    This is internal-only and must not be exposed as an API endpoint.
    """
    if (
        not isinstance(session_token, str)
        or not session_token
        or session_token.strip() != session_token
        or any(character.isspace() for character in session_token)
    ):
        raise PermissionError("Valid authenticated session required.")

    user = get_session_user(db, session_token)

    if (
        user is None
        or getattr(user, "is_active", None) is not True
        or not isinstance(getattr(user, "id", None), UUID)
    ):
        raise PermissionError("Valid authenticated session required.")

    stage_persisted_admin_resolution(
        db,
        project_id=project_id,
        ownership_id=ownership_id,
        data_source_id=data_source_id,
        evidence_id=evidence_id,
        trusted_actor_user_id=user.id,
        session_token=session_token,
        reason=reason,
        evidence_reference=evidence_reference,
    )
