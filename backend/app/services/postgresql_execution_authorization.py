"""Authorize registered PostgreSQL connections for Data Quality execution.

This module does not connect to client databases or persist credentials.
"""

from app.models.postgresql_connection_identity import PostgreSQLConnectionIdentity


class PostgreSQLExecutionAuthorizationError(ValueError):
    """The registered PostgreSQL connection is not eligible for execution."""


def authorize_postgresql_execution_connection(
    db,
    *,
    data_source_id,
    username,
):
    """Require an existing, verified connection before execution."""
    identity = db.get(PostgreSQLConnectionIdentity, data_source_id)

    if identity is None:
        raise PostgreSQLExecutionAuthorizationError(
            "Registered PostgreSQL connection not found."
        )

    if not identity.is_verified or identity.verified_at is None:
        raise PostgreSQLExecutionAuthorizationError(
            "PostgreSQL connection verification is required before execution."
        )

    from app.core.config import settings
    from app.services.postgresql_verification_policy import (
        require_postgresql_verification_configuration,
    )

    require_postgresql_verification_configuration(settings)

    from app.services.postgresql_verification_policy import (
        require_approved_postgresql_destination,
    )

    require_approved_postgresql_destination(
        host=identity.host,
        port=identity.port,
        allowed_destinations=settings.postgresql_verification_allowed_destinations,
    )

    from app.services.postgresql_verification_policy import (
        require_postgresql_trusted_ca_file,
    )

    require_postgresql_trusted_ca_file(
        settings.postgresql_verification_ssl_root_cert
    )

    from app.services.postgresql_verification_policy import (
        resolve_approved_postgresql_ip,
    )

    approved_ip = resolve_approved_postgresql_ip(
        host=identity.host,
        port=identity.port,
        allowed_networks=settings.postgresql_verification_allowed_ip_networks,
    )

    from app.connectors.database.base import DatabaseConnectionConfig

    return PostgreSQLExecutionConnectionSnapshot(
        config=DatabaseConnectionConfig(
            host=identity.host,
            port=identity.port,
            database=identity.database_name,
            username=username,
            ssl_mode="verify-full",
            host_address=approved_ip,
        ),
        connection_revision=identity.connection_revision,
    )


def revalidate_postgresql_execution_connection(
    db,
    *,
    data_source_id,
    expected_host,
    expected_port,
    expected_database,
    expected_revision,
):
    """Recheck the registered connection under a row lock before recording results."""
    current_identity = (
        db.query(PostgreSQLConnectionIdentity)
        .filter(
            PostgreSQLConnectionIdentity.data_source_id == data_source_id
        )
        .with_for_update()
        .one_or_none()
    )

    if current_identity is None:
        raise PostgreSQLExecutionAuthorizationError(
            "Registered PostgreSQL connection changed or was removed."
        )

    if (
        current_identity.host != expected_host
        or current_identity.port != expected_port
        or current_identity.database_name != expected_database
        or current_identity.connection_revision != expected_revision
    ):
        raise PostgreSQLExecutionAuthorizationError(
            "Registered PostgreSQL connection changed during execution."
        )

    if (
        not current_identity.is_verified
        or current_identity.verified_at is None
    ):
        raise PostgreSQLExecutionAuthorizationError(
            "PostgreSQL connection verification was revoked."
        )

    return current_identity
from dataclasses import dataclass

from app.connectors.database.base import DatabaseConnectionConfig


@dataclass(frozen=True)
class PostgreSQLExecutionConnectionSnapshot:
    """Immutable authorization result for a registered PostgreSQL connection."""

    config: DatabaseConnectionConfig
    connection_revision: int

    @property
    def host(self):
        return self.config.host

    @property
    def port(self):
        return self.config.port

    @property
    def database(self):
        return self.config.database

    @property
    def username(self):
        return self.config.username

    @property
    def ssl_mode(self):
        return self.config.ssl_mode

    @property
    def host_address(self):
        return self.config.host_address
