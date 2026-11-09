"""Internal protected admission coordination for Phase 5E.

NOT connected to API routes, workers, runtime admission, or source I/O.

This function coordinates one already-authorized, trusted admission
stage. It does not perform project authorization or feature-flag
checks itself; those must be enforced by a future controlled caller.

Do not automatically retry if admission commit or verification fails.
A commit exception may mean the database transaction actually
committed, even if the client did not receive confirmation.

Successful verification is point-in-time evidence of protection,
not permission to begin source measurement.
"""

from collections.abc import Callable
from uuid import UUID

from app.services.data_quality_execution_coordinator_transaction import (
    run_coordinator_transaction,
)
from app.services.data_quality_execution_coordinator_committed_snapshot import (
    verify_committed_protection,
)


def commit_and_verify_protected_admission(
    *,
    session_factory: Callable,
    project_id: UUID,
    stage_admission: Callable,
) -> UUID:
    """Commit one admission stage, then verify its persisted protection.

    The trusted stage must return an execution UUID, not an ORM object.
    Both stages use independently created database sessions.
    """
    if not callable(session_factory):
        raise ValueError("A callable session factory is required.")

    if not isinstance(project_id, UUID):
        raise ValueError("Invalid admission project identity.")

    if not callable(stage_admission):
        raise ValueError("A callable admission stage is required.")

    execution_id = run_coordinator_transaction(
        session_factory=session_factory,
        stage=stage_admission,
    )

    if not isinstance(execution_id, UUID):
        raise ValueError(
            "Protected admission must return an execution UUID."
        )

    verified_execution_id = verify_committed_protection(
        session_factory=session_factory,
        project_id=project_id,
        execution_id=execution_id,
        expected_status="pending",
    )

    if (
        not isinstance(verified_execution_id, UUID)
        or verified_execution_id != execution_id
    ):
        raise ValueError(
            "Committed admission verification identity mismatch."
        )

    return execution_id
