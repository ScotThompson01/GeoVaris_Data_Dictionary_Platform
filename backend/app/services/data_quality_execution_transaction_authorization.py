"""Transaction-scoped validation of persisted execution connection authorization.

Internal Phase 5E component. Used by internal protected-start staging only.
Not integrated with routes, workers, runtime admission, or source measurement.

The caller owns an existing database transaction. This function acquires
row locks, performs checks, and never commits, rolls back, retries, releases
capacity, or opens a client-source connection.

Returned identifiers are not permission to start or measure source data.
The caller must maintain transaction and lock protections through its
subsequent state transition.
"""

from datetime import datetime
from ipaddress import ip_address
from uuid import UUID

from sqlalchemy import select

from app.models.data_quality_execution_connection_authorization import (
    DataQualityExecutionConnectionAuthorization,
)
from app.models.data_quality_workload_ownership import (
    DataQualityWorkloadOwnership,
)
from app.services.postgresql_execution_authorization import (
    revalidate_postgresql_execution_connection,
)


class TransactionConnectionAuthorizationUnavailableError(ValueError):
    """Required transaction-scoped authorization is unavailable."""


def validate_locked_execution_connection_authorization(
    db,
    *,
    execution_id: UUID,
    project_id: UUID,
    data_source_id: UUID,
) -> tuple[UUID, int]:
    """Validate locked ownership, persisted evidence, and connection identity.

    Only non-secret source and revision identifiers are returned.
    The function does not establish prior transaction history or authorize
    network access. All locks are owned by the caller's transaction.
    """
    if db is None:
        raise ValueError("An existing database session is required.")

    if not all(
        isinstance(value, UUID)
        for value in (execution_id, project_id, data_source_id)
    ):
        raise ValueError("Valid execution, project, and source UUIDs are required.")

    ownership = db.scalar(
        select(DataQualityWorkloadOwnership)
        .where(
            DataQualityWorkloadOwnership.execution_id == execution_id,
            DataQualityWorkloadOwnership.project_id == project_id,
        )
        .with_for_update()
    )

    if ownership is None:
        raise TransactionConnectionAuthorizationUnavailableError(
            "Committed workload ownership is unavailable."
        )

    if ownership.data_source_id != data_source_id:
        raise TransactionConnectionAuthorizationUnavailableError(
            "Workload ownership source identity mismatch."
        )

    if (
        ownership.execution_id != execution_id
        or ownership.project_id != project_id
        or not isinstance(data_source_id, UUID)
        or ownership.ownership_state != "reserved"
        or ownership.released_at is not None
        or ownership.release_actor is not None
        or ownership.release_reason is not None
        or ownership.release_evidence_reference is not None
    ):
        raise TransactionConnectionAuthorizationUnavailableError(
            "Workload ownership is invalid or no longer reserved."
        )

    evidence = db.scalar(
        select(DataQualityExecutionConnectionAuthorization)
        .where(
            DataQualityExecutionConnectionAuthorization.execution_id
            == execution_id,
            DataQualityExecutionConnectionAuthorization.project_id
            == project_id,
            DataQualityExecutionConnectionAuthorization.data_source_id
            == data_source_id,
        )
        .with_for_update()
    )

    if evidence is None:
        raise TransactionConnectionAuthorizationUnavailableError(
            "Persisted connection authorization is unavailable."
        )

    revision = evidence.connection_revision

    if (
        evidence.execution_id != execution_id
        or evidence.project_id != project_id
        or evidence.data_source_id != data_source_id
        or type(revision) is not int
        or revision <= 0
        or not isinstance(evidence.authorized_host, str)
        or not evidence.authorized_host.strip()
        or type(evidence.authorized_port) is not int
        or not 1 <= evidence.authorized_port <= 65535
        or not isinstance(evidence.authorized_database, str)
        or not evidence.authorized_database.strip()
        or not isinstance(evidence.authorized_ip, str)
        or not evidence.authorized_ip.strip()
        or not isinstance(evidence.authorized_at, datetime)
        or evidence.authorized_at.tzinfo is None
        or evidence.authorized_at.utcoffset() is None
    ):
        raise TransactionConnectionAuthorizationUnavailableError(
            "Persisted connection authorization is invalid."
        )

    try:
        ip_address(evidence.authorized_ip)
    except ValueError as exc:
        raise TransactionConnectionAuthorizationUnavailableError(
            "Persisted authorization address is invalid."
        ) from exc

    current_identity = revalidate_postgresql_execution_connection(
        db,
        data_source_id=data_source_id,
        expected_host=evidence.authorized_host,
        expected_port=evidence.authorized_port,
        expected_database=evidence.authorized_database,
        expected_revision=revision,
    )

    if (
        current_identity is None
        or current_identity.data_source_id != data_source_id
        or current_identity.host != evidence.authorized_host
        or current_identity.port != evidence.authorized_port
        or current_identity.database_name != evidence.authorized_database
        or current_identity.connection_revision != revision
        or not current_identity.is_verified
        or current_identity.verified_at is None
    ):
        raise TransactionConnectionAuthorizationUnavailableError(
            "Current PostgreSQL connection identity does not match."
        )

    return data_source_id, revision
