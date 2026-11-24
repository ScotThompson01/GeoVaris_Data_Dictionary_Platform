"""Authorize registered PostgreSQL destinations for basic profiling.

This service validates connection eligibility and current destination
policy. It does not grant user, scan, field, or workload authorization,
connect to a client database, or persist credentials.

The future orchestration workflow must enforce all remaining execution
requirements before invoking a profiling connector.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.connectors.database.base import DatabaseConnectionConfig
from app.core.config import settings
from app.models.postgresql_connection_identity import (
    PostgreSQLConnectionIdentity,
)
from app.services import postgresql_verification_policy as policy
from app.services.postgresql_profiling_execution_policy import (
    require_postgresql_profiling_execution_enabled,
)


class PostgreSQLProfilingConnectionAuthorizationError(ValueError):
    """A registered connection is not eligible for profiling."""


@dataclass(frozen=True)
class PostgreSQLProfilingConnectionSnapshot:
    """Non-secret, source-bound profiling connection metadata.

    This snapshot is not an execution admission token.
    """

    data_source_id: UUID
    connection_revision: int
    config: DatabaseConnectionConfig


def authorize_postgresql_profiling_connection(
    *,
    db: Session,
    data_source_id: UUID,
    username: str,
) -> PostgreSQLProfilingConnectionSnapshot:
    """Validate registered connection eligibility for basic profiling.

    Current deployment and destination policies must pass before
    returning a TLS-protected, IP-pinned connection configuration.

    DNS resolution may occur through the approved verification policy.
    No source database connection or metadata write is performed.
    """

    require_postgresql_profiling_execution_enabled(settings)

    if not isinstance(data_source_id, UUID):
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "A valid data source UUID is required."
        )

    if not isinstance(username, str) or not username.strip():
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "A valid PostgreSQL username is required."
        )

    identity = db.get(
        PostgreSQLConnectionIdentity,
        data_source_id,
    )

    if identity is None:
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Registered PostgreSQL connection not found."
        )

    if identity.data_source_id != data_source_id:
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Registered PostgreSQL connection identity mismatch."
        )

    if identity.is_verified is not True or identity.verified_at is None:
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "PostgreSQL connection verification is required."
        )

    revision = identity.connection_revision

    if type(revision) is not int or revision <= 0:
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Registered PostgreSQL connection revision is invalid."
        )

    host = identity.host
    port = identity.port
    database = identity.database_name

    if not isinstance(host, str) or not host.strip():
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Registered PostgreSQL hostname is invalid."
        )

    if type(port) is not int or not 1 <= port <= 65535:
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Registered PostgreSQL port is invalid."
        )

    if not isinstance(database, str) or not database.strip():
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Registered PostgreSQL database name is invalid."
        )

    policy.require_postgresql_verification_configuration(settings)

    policy.require_approved_postgresql_destination(
        host=host,
        port=port,
        allowed_destinations=(
            settings.postgresql_verification_allowed_destinations
        ),
    )

    policy.require_postgresql_trusted_ca_file(
        settings.postgresql_verification_ssl_root_cert
    )

    approved_ip = policy.resolve_approved_postgresql_ip(
        host=host,
        port=port,
        allowed_networks=(
            settings.postgresql_verification_allowed_ip_networks
        ),
    )

    return PostgreSQLProfilingConnectionSnapshot(
        data_source_id=data_source_id,
        connection_revision=revision,
        config=DatabaseConnectionConfig(
            host=host,
            port=port,
            database=database,
            username=username,
            ssl_mode="verify-full",
            host_address=approved_ip,
        ),
    )
