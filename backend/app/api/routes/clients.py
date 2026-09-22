import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.db.session import get_db
from app.models.client import Client
from app.models.client_access import ClientAccess
from app.schemas.client import ClientCreate, ClientRead
from app.services.client_authorization import require_client_access

router = APIRouter()


@router.get("", response_model=list[ClientRead])
def list_clients(
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    query = (
        select(Client)
        .join(ClientAccess, ClientAccess.client_id == Client.id)
        .where(ClientAccess.user_id == session.user.id)
        .order_by(Client.name)
    )
    return db.scalars(query).all()


@router.post("", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(
    payload: ClientCreate,
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    # Client provisioning is disabled until an explicit permission
    # and provisioning workflow is implemented.
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Client creation is not permitted.",
    )


@router.get("/{client_id}", response_model=ClientRead)
def get_client(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")

    require_client_access(
        db,
        user_id=session.user.id,
        client_id=client_id,
    )
    return client
