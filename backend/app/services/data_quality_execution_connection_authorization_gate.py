"""Fail-closed prerequisite for independently committed connection authorization.

This service does not authorize runtime execution, perform source access,
commit transactions, retry failures, or release reserved capacity.
"""

from uuid import UUID

from app.services.data_quality_execution_committed_connection_authorization import (
    verify_committed_connection_authorization,
)


def require_committed_connection_authorization(
    *,
    session_factory,
    execution_id: UUID,
    project_id: UUID,
    data_source_id: UUID,
    expected_connection_revision: int,
) -> UUID:
    """Require verified authorization for the exact connection identity.

    The verifier uses a separate database session to inspect committed
    authorization evidence. Its exceptions propagate without recovery.
    """
    if not callable(session_factory):
        raise ValueError("A session factory is required.")

    if not all(
        isinstance(value, UUID)
        for value in (execution_id, project_id, data_source_id)
    ):
        raise ValueError("Valid authorization UUID identities are required.")

    if (
        type(expected_connection_revision) is not int
        or expected_connection_revision <= 0
    ):
        raise ValueError("A positive connection revision is required.")

    verified_execution_id = verify_committed_connection_authorization(
        session_factory=session_factory,
        execution_id=execution_id,
        project_id=project_id,
        data_source_id=data_source_id,
        expected_connection_revision=expected_connection_revision,
    )

    if (
        not isinstance(verified_execution_id, UUID)
        or verified_execution_id != execution_id
    ):
        raise ValueError(
            "Committed connection authorization identity mismatch."
        )

    return execution_id