import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientRead

router = APIRouter()


@router.get("", response_model=list[ClientRead])
def list_clients(db: Session = Depends(get_db)):
    return db.scalars(select(Client).order_by(Client.name)).all()


@router.post("", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(payload: ClientCreate, db: Session = Depends(get_db)):
    client = Client(name=payload.name.strip(), description=payload.description)
    db.add(client)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A client with this name already exists.",
        )

    db.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientRead)
def get_client(client_id: uuid.UUID, db: Session = Depends(get_db)):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    return client
