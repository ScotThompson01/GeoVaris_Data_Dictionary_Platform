"""Verify registered PostgreSQL destinations without persisting credentials."""

from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session

from app.connectors.database.base import DatabaseConnectionConfig
from app.core.config import settings
from app.services.postgresql_verification_policy import (
    require_approved_postgresql_destination,
    require_postgresql_trusted_ca_file,
    require_postgresql_verification_configuration,
    resolve_approved_postgresql_ip,
)
from app.connectors.database.postgresql_connector import PostgreSQLConnector
from app.models.postgresql_connection_identity import PostgreSQLConnectionIdentity


class PostgreSQLConnectionIdentityNotRegisteredError(ValueError):
    """The requested PostgreSQL connection identity is not registered."""


class PostgreSQLConnectionDestinationChangedError(ValueError):
    """The registered destination changed during verification."""


def verify_postgresql_connection(
    db: Session,
    *,
    data_source_id: uuid.UUID,
    username: str,
    password: str | None,
    connect_timeout_seconds: int = 10,
) -> PostgreSQLConnectionIdentity:
    """Validate a registered destination and record successful verification."""
    # Snapshot the destination without holding a row lock during network I/O.
    identity = db.get(PostgreSQLConnectionIdentity, data_source_id)

    if identity is None:
        db.rollback()
        raise PostgreSQLConnectionIdentityNotRegisteredError(
            "PostgreSQL connection identity not registered."
        )

    destination = (
        identity.host,
        identity.port,
        identity.database_name,
    )
    connection_revision = identity.connection_revision

    # End the read transaction before connecting to the client database.
    db.rollback()

    config = DatabaseConnectionConfig(
        host=destination[0],
        port=destination[1],
        database=destination[2],
        username=username,
        ssl_mode="verify-full",
        connect_timeout_seconds=connect_timeout_seconds,
    )

    # Reject unauthorized destinations before attempting network access.
    require_postgresql_verification_configuration(settings)
    require_approved_postgresql_destination(
        host=destination[0],
        port=destination[1],
        allowed_destinations=(
            settings.postgresql_verification_allowed_destinations
        ),
    )

    # Reject missing or unreadable CA files before network access.
    require_postgresql_trusted_ca_file(
        settings.postgresql_verification_ssl_root_cert
    )

    # Resolve once and authorize every returned destination IP.
    approved_ip = resolve_approved_postgresql_ip(
        host=destination[0],
        port=destination[1],
        allowed_networks=(
            settings.postgresql_verification_allowed_ip_networks
        ),
    )

    # Pin the approved IP while retaining the hostname for TLS verify-full.
    from dataclasses import replace

    config = replace(config, host_address=approved_ip)

    PostgreSQLConnector().validate_connection(
        config,
        password=password,
        ssl_root_cert=settings.postgresql_verification_ssl_root_cert,
    )

    # Lock and recheck the destination before recording verification.
    try:
        current_identity = (
            db.query(PostgreSQLConnectionIdentity)
            .filter(
                PostgreSQLConnectionIdentity.data_source_id == data_source_id
            )
            .with_for_update()
            .one_or_none()
        )

        if current_identity is None or (
            current_identity.host,
            current_identity.port,
            current_identity.database_name,
        ) != destination or (
            current_identity.connection_revision != connection_revision
        ):
            raise PostgreSQLConnectionDestinationChangedError(
                "Registered PostgreSQL destination changed during verification."
            )

        current_identity.is_verified = True
        current_identity.verified_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(current_identity)
        return current_identity
    except Exception:
        db.rollback()
        raise
