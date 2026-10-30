"""Read-only access to registered PostgreSQL connection identities."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.db.session import get_db
from app.models.data_source import DataSource
from app.models.postgresql_connection_identity import PostgreSQLConnectionIdentity
from app.schemas.postgresql_connection_identity import (
    PostgreSQLConnectionIdentityCreate,
    PostgreSQLConnectionIdentityRead,
    PostgreSQLConnectionIdentityUpdate,
    PostgreSQLConnectionVerificationRequest,
)
from app.services.project_authorization import (
    require_data_source_connection_manager,
)

from app.services.postgresql_connection_verification import (
    PostgreSQLConnectionDestinationChangedError,
    PostgreSQLConnectionIdentityNotRegisteredError,
    verify_postgresql_connection,
)

from app.services.postgresql_verification_policy import (
    PostgreSQLVerificationPolicyError,
)

router = APIRouter()


@router.get(
    "/{data_source_id}/postgresql-connection",
    response_model=PostgreSQLConnectionIdentityRead,
)
def get_postgresql_connection_identity(
    data_source_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    """Return a registered destination to an authorized connection manager."""
    data_source = db.get(DataSource, data_source_id)

    if data_source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found.",
        )

    try:
        require_data_source_connection_manager(
            db,
            user_id=session.user.id,
            project_id=data_source.project_id,
        )
    except HTTPException as exc:
        if exc.status_code != status.HTTP_404_NOT_FOUND:
            raise
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found.",
        ) from None

    if data_source.source_type != "postgresql":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data source is not PostgreSQL.",
        )

    identity = db.get(
        PostgreSQLConnectionIdentity,
        data_source_id,
    )

    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PostgreSQL connection identity not registered.",
        )

    return identity


@router.put(
    "/{data_source_id}/postgresql-connection",
    response_model=PostgreSQLConnectionIdentityRead,
)
def put_postgresql_connection_identity(
    data_source_id: uuid.UUID,
    payload: PostgreSQLConnectionIdentityUpdate,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    """Register a non-secret PostgreSQL destination for an authorized project."""
    data_source = db.scalar(
        select(DataSource)
        .where(DataSource.id == data_source_id)
        .with_for_update()
    )

    if data_source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found.",
        )

    try:
        require_data_source_connection_manager(
            db,
            user_id=session.user.id,
            project_id=data_source.project_id,
        )
    except HTTPException as exc:
        if exc.status_code != status.HTTP_404_NOT_FOUND:
            raise
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found.",
        ) from None

    if data_source.source_type != "postgresql" or data_source.connection_mode != "database":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data source must be a PostgreSQL database.",
        )

    identity = db.get(PostgreSQLConnectionIdentity, data_source_id)

    if identity is None:
        identity = PostgreSQLConnectionIdentity(
            data_source_id=data_source_id,
            host=payload.host,
            port=payload.port,
            database_name=payload.database_name,
            connection_revision=1,
            is_verified=False,
            verified_at=None,
        )
        db.add(identity)
    else:
        expected = (
            payload.expected_current_host,
            payload.expected_current_port,
            payload.expected_current_database_name,
        )
        current = (
            identity.host,
            identity.port,
            identity.database_name,
        )

        if any(value is None for value in expected):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Expected current connection details are required for updates.",
            )

        if expected != current:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Connection details changed. Reload the current settings before updating.",
            )

        if (
            identity.host != payload.host
            or identity.port != payload.port
            or identity.database_name != payload.database_name
        ):
            identity.host = payload.host
            identity.port = payload.port
            identity.database_name = payload.database_name
            identity.connection_revision += 1
            identity.is_verified = False
            identity.verified_at = None

    db.commit()
    db.refresh(identity)
    return identity



@router.post(
    "/{data_source_id}/postgresql-connection/verify",
    response_model=PostgreSQLConnectionIdentityRead,
)
def verify_postgresql_connection_route(
    data_source_id: uuid.UUID,
    payload: PostgreSQLConnectionVerificationRequest,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    """Verify an authorized registered PostgreSQL destination."""
    data_source = db.get(DataSource, data_source_id)

    if data_source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found.",
        )

    try:
        require_data_source_connection_manager(
            db,
            user_id=session.user.id,
            project_id=data_source.project_id,
        )
    except HTTPException as exc:
        if exc.status_code != status.HTTP_404_NOT_FOUND:
            raise
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found.",
        ) from None

    if (
        data_source.source_type != "postgresql"
        or data_source.connection_mode != "database"
        or not data_source.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data source must be an active PostgreSQL database.",
        )

    try:
        return verify_postgresql_connection(
            db,
            data_source_id=data_source_id,
            username=payload.username,
            password=(
                payload.password.get_secret_value()
                if payload.password is not None
                else None
            ),
            connect_timeout_seconds=payload.connect_timeout_seconds,
        )
    except PostgreSQLConnectionDestinationChangedError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "PostgreSQL connection settings changed. "
                "Reload the connection settings and try again."
            ),
        ) from None
    except PostgreSQLConnectionIdentityNotRegisteredError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PostgreSQL connection identity not registered.",
        ) from None
    except PostgreSQLVerificationPolicyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostgreSQL connection verification is unavailable.",
        ) from None
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="PostgreSQL connection verification failed.",
        ) from None
