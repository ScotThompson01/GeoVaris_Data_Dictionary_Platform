"""Independent read-only inspection of persisted connection authorization.

Internal Phase 5E component. Not connected to API routes, workers, runtime
admission, or client-source measurement.

Visibility through a new database session is not proof of transaction
history, continued validity, or permission to execute a measurement.
"""

from datetime import datetime
from ipaddress import ip_address
from uuid import UUID

from sqlalchemy import select

from app.models.data_quality_execution_connection_authorization import (
    DataQualityExecutionConnectionAuthorization,
)


class CommittedConnectionAuthorizationUnavailableError(ValueError):
    """The required persisted authorization evidence is unavailable."""


def verify_committed_connection_authorization(
    *,
    session_factory,
    execution_id: UUID,
    project_id: UUID,
    data_source_id: UUID,
    expected_connection_revision: int,
) -> UUID:
    """Inspect authorization evidence using an independent database session.

    This function never creates or updates authorization evidence, commits
    transactions, acquires row locks, or connects to a client data source.
    It is not a runtime measurement authorization gate.
    """
    if not callable(session_factory):
        raise ValueError("An independent session factory is required.")

    if (
        not isinstance(execution_id, UUID)
        or not isinstance(project_id, UUID)
        or not isinstance(data_source_id, UUID)
    ):
        raise ValueError("Valid UUID identifiers are required.")

    if (
        type(expected_connection_revision) is not int
        or expected_connection_revision <= 0
    ):
        raise ValueError("A positive connection revision is required.")

    db = session_factory()

    try:
        evidence = db.scalar(
            select(DataQualityExecutionConnectionAuthorization).where(
                DataQualityExecutionConnectionAuthorization.execution_id
                == execution_id,
                DataQualityExecutionConnectionAuthorization.project_id
                == project_id,
                DataQualityExecutionConnectionAuthorization.data_source_id
                == data_source_id,
                DataQualityExecutionConnectionAuthorization.connection_revision
                == expected_connection_revision,
            )
        )

        if evidence is None:
            raise CommittedConnectionAuthorizationUnavailableError(
                "Matching persisted authorization evidence is unavailable."
            )

        if (
            evidence.execution_id != execution_id
            or evidence.project_id != project_id
            or evidence.data_source_id != data_source_id
            or type(evidence.connection_revision) is not int
            or evidence.connection_revision != expected_connection_revision
        ):
            raise CommittedConnectionAuthorizationUnavailableError(
                "Persisted authorization identifiers do not match."
            )

        if (
            not isinstance(evidence.authorized_host, str)
            or not evidence.authorized_host.strip()
            or type(evidence.authorized_port) is not int
            or not 1 <= evidence.authorized_port <= 65535
            or not isinstance(evidence.authorized_database, str)
            or not evidence.authorized_database.strip()
            or not isinstance(evidence.authorized_ip, str)
            or not evidence.authorized_ip.strip()
        ):
            raise CommittedConnectionAuthorizationUnavailableError(
                "Persisted authorization destination is invalid."
            )

        try:
            ip_address(evidence.authorized_ip)
        except ValueError as exc:
            raise CommittedConnectionAuthorizationUnavailableError(
                "Persisted authorization IP address is invalid."
            ) from exc

        if (
            not isinstance(evidence.authorized_at, datetime)
            or evidence.authorized_at.tzinfo is None
            or evidence.authorized_at.utcoffset() is None
        ):
            raise CommittedConnectionAuthorizationUnavailableError(
                "Persisted authorization timestamp is invalid."
            )

        # Only return an immutable identifier. Never return an ORM object
        # whose state depends on the lifetime of the verification session.
        return execution_id

    finally:
        db.close()
