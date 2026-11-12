"""Require independently verified ownership and connection authorization.

This gate does not start an execution, perform measurements, reserve capacity,
or certify that independent reads form an atomic database snapshot.
The protected-start integration must address concurrency and revalidation.
"""

from uuid import UUID

from app.services.data_quality_execution_committed_workload_ownership import (
    verify_committed_workload_ownership,
)
from app.services.data_quality_execution_connection_authorization_gate import (
    require_committed_connection_authorization,
)


def require_committed_execution_prerequisites(
    *,
    session_factory,
    execution_id: UUID,
    project_id: UUID,
    data_source_id: UUID,
    expected_connection_revision: int,
) -> UUID:
    """Require both independent checks for the exact expected identities.

    Errors from either prerequisite propagate. Failure never triggers retry,
    resource release, a protected start, or a client-source measurement.
    """
    if not callable(session_factory):
        raise ValueError("A session factory is required.")

    if not all(
        isinstance(value, UUID)
        for value in (execution_id, project_id, data_source_id)
    ):
        raise ValueError("Valid execution prerequisite UUIDs are required.")

    if (
        type(expected_connection_revision) is not int
        or expected_connection_revision <= 0
    ):
        raise ValueError("A positive connection revision is required.")

    verified_ownership_execution_id = verify_committed_workload_ownership(
        session_factory=session_factory,
        execution_id=execution_id,
        project_id=project_id,
        data_source_id=data_source_id,
    )

    if (
        not isinstance(verified_ownership_execution_id, UUID)
        or verified_ownership_execution_id != execution_id
    ):
        raise ValueError("Committed workload ownership identity mismatch.")

    verified_connection_execution_id = (
        require_committed_connection_authorization(
            session_factory=session_factory,
            execution_id=execution_id,
            project_id=project_id,
            data_source_id=data_source_id,
            expected_connection_revision=expected_connection_revision,
        )
    )

    if (
        not isinstance(verified_connection_execution_id, UUID)
        or verified_connection_execution_id != execution_id
    ):
        raise ValueError("Committed connection authorization identity mismatch.")

    return execution_id