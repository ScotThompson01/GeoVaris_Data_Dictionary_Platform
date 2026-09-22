"""Reusable checks for explicit client access."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.client_access import ClientAccess


def require_client_access(
    db: Session,
    *,
    user_id: uuid.UUID,
    client_id: uuid.UUID,
) -> None:
    """Raise 404 unless the user has an explicit grant for this client."""
    grant_id = db.scalar(
        select(ClientAccess.id).where(
            ClientAccess.user_id == user_id,
            ClientAccess.client_id == client_id,
        )
    )

    if grant_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found.",
        )
