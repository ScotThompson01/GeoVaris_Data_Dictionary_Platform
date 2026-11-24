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



def revalidate_postgresql_profiling_connection(
    *,
    db: Session,
    data_source_id: UUID,
    snapshot: PostgreSQLProfilingConnectionSnapshot,
) -> None:
    """Revalidate a profiling connection in the caller's transaction.

    Refresh and lock the registered connection identity, compare it
    against the authorization snapshot, and reapply current destination
    policies.

    The caller owns the transaction and must release the row lock.
    The caller must supply a trusted internal snapshot and a suitable
    transaction without pending connection identity modifications.

    DNS resolution may occur through the approved verification policy.
    No client database connection, metadata write, commit, or rollback
    is performed.

    Successful revalidation is not permission to execute profiling.
    """
    require_postgresql_profiling_execution_enabled(settings)

    if not isinstance(data_source_id, UUID):
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "A valid data source UUID is required."
        )

    if not isinstance(
        snapshot,
        PostgreSQLProfilingConnectionSnapshot,
    ):
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "A valid profiling connection snapshot is required."
        )

    if (
        not isinstance(snapshot.data_source_id, UUID)
        or snapshot.data_source_id != data_source_id
    ):
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Profiling connection snapshot source mismatch."
        )

    if (
        type(snapshot.connection_revision) is not int
        or snapshot.connection_revision <= 0
    ):
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Profiling connection snapshot revision is invalid."
        )

    config = snapshot.config

    if not isinstance(config, DatabaseConnectionConfig):
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Profiling connection snapshot configuration is invalid."
        )

    if not isinstance(config.host, str) or not config.host.strip():
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Profiling connection snapshot hostname is invalid."
        )

    if type(config.port) is not int or not 1 <= config.port <= 65535:
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Profiling connection snapshot port is invalid."
        )

    if (
        not isinstance(config.database, str)
        or not config.database.strip()
    ):
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Profiling connection snapshot database name is invalid."
        )

    if (
        not isinstance(config.username, str)
        or not config.username.strip()
    ):
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Profiling connection snapshot username is invalid."
        )

    if config.ssl_mode != "verify-full":
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Profiling connection requires TLS verify-full."
        )

    if (
        not isinstance(config.host_address, str)
        or not config.host_address.strip()
    ):
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Profiling connection snapshot approved IP is invalid."
        )

    # A row lock alone does not refresh an existing ORM identity.
    # Refresh the selected identity and suppress automatic flushing.
    current_identity = (
        db.query(PostgreSQLConnectionIdentity)
        .filter(
            PostgreSQLConnectionIdentity.data_source_id
            == data_source_id
        )
        .execution_options(
            populate_existing=True,
            autoflush=False,
        )
        .with_for_update()
        .one_or_none()
    )

    if current_identity is None:
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Registered PostgreSQL connection changed or was removed."
        )

    if current_identity.data_source_id != data_source_id:
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Registered PostgreSQL connection identity mismatch."
        )

    if (
        type(current_identity.connection_revision) is not int
        or current_identity.connection_revision <= 0
        or current_identity.connection_revision
        != snapshot.connection_revision
    ):
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Registered PostgreSQL connection revision changed."
        )

    if (
        not isinstance(current_identity.host, str)
        or current_identity.host != config.host
        or type(current_identity.port) is not int
        or current_identity.port != config.port
        or not isinstance(current_identity.database_name, str)
        or current_identity.database_name != config.database
    ):
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Registered PostgreSQL connection destination changed."
        )

    if (
        current_identity.is_verified is not True
        or current_identity.verified_at is None
    ):
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Registered PostgreSQL connection verification is required."
        )

    # Reapply current deployment destination policies rather than
    # treating the original snapshot as permanent authorization.
    policy.require_postgresql_verification_configuration(settings)

    policy.require_approved_postgresql_destination(
        host=current_identity.host,
        port=current_identity.port,
        allowed_destinations=(
            settings.postgresql_verification_allowed_destinations
        ),
    )

    policy.require_postgresql_trusted_ca_file(
        settings.postgresql_verification_ssl_root_cert
    )

    approved_ip = policy.resolve_approved_postgresql_ip(
        host=current_identity.host,
        port=current_identity.port,
        allowed_networks=(
            settings.postgresql_verification_allowed_ip_networks
        ),
    )

    if approved_ip != config.host_address:
        raise PostgreSQLProfilingConnectionAuthorizationError(
            "Approved PostgreSQL IP no longer matches the snapshot."
        )

    # No execution token is issued. Transaction ownership and all
    # remaining execution authorization belong to the caller.
    return None
