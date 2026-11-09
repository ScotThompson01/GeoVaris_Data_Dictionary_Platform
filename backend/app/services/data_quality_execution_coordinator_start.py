"""Internal protected execution-start coordination for Phase 5E.

NOT connected to API routes, runtime admission, workers, or source I/O.

The caller must supply a trusted, independently authorized staging
callback. The callback must stage only the protected PENDING -> RUNNING
transition and return the matching execution UUID.

This coordinator verifies persisted PENDING protection before starting
the transition, commits the staged transition, then verifies persisted
RUNNING protection using a separate database session.

Neither a successful verification nor a committed RUNNING transition
authorizes client-source measurement by itself.

Do not retry automatically after any failure. A database commit
exception may have an uncertain server-side outcome.
"""

from collections.abc import Callable
from uuid import UUID

from app.services.data_quality_execution_coordinator_transaction import (
    run_coordinator_transaction,
)
from app.services.data_quality_execution_coordinator_committed_snapshot import (
    verify_committed_protection,
)


def commit_and_verify_protected_start(
    *,
    session_factory: Callable,
    project_id: UUID,
    execution_id: UUID,
    stage_start: Callable,
) -> UUID:
    """Commit a trusted RUNNING transition between two protection checks."""
    if not callable(session_factory):
        raise ValueError("A callable session factory is required.")

    if (
        not isinstance(project_id, UUID)
        or not isinstance(execution_id, UUID)
    ):
        raise ValueError("Invalid protected execution identity.")

    if not callable(stage_start):
        raise ValueError("A callable protected-start stage is required.")

    pending_id = verify_committed_protection(
        session_factory=session_factory,
        project_id=project_id,
        execution_id=execution_id,
        expected_status="pending",
    )

    if not isinstance(pending_id, UUID) or pending_id != execution_id:
        raise ValueError(
            "PENDING protection verification identity mismatch."
        )

    started_id = run_coordinator_transaction(
        session_factory=session_factory,
        stage=stage_start,
    )

    if not isinstance(started_id, UUID) or started_id != execution_id:
        raise ValueError(
            "RUNNING transition execution identity mismatch."
        )

    running_id = verify_committed_protection(
        session_factory=session_factory,
        project_id=project_id,
        execution_id=execution_id,
        expected_status="running",
    )

    if not isinstance(running_id, UUID) or running_id != execution_id:
        raise ValueError(
            "RUNNING protection verification identity mismatch."
        )

    return execution_id
