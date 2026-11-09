"""Internal Phase 5E protected admission/start sequencing.

NOT connected to API routes, workers, runtime admission, or source I/O.

Only a trusted, independently authorized internal caller may supply
staging callbacks. The callbacks must perform database staging only.

The admission coordinator independently commits and verifies PENDING
protection. The start coordinator then verifies PENDING protection
again, commits the RUNNING transition, and independently verifies
RUNNING protection.

Do not automatically retry after an error. A failed verification or
an exception during commit may leave committed protection records
that require independent inspection and manual review.

Successful sequencing does NOT authorize client-source measurement.
The runtime admission feature flag remains a separate requirement.
"""

from collections.abc import Callable
from uuid import UUID

from app.services.data_quality_execution_coordinator_admission import (
    commit_and_verify_protected_admission,
)
from app.services.data_quality_execution_coordinator_start import (
    commit_and_verify_protected_start,
)


def coordinate_protected_admission_and_start(
    *,
    session_factory: Callable,
    project_id: UUID,
    stage_admission: Callable,
    stage_start_factory: Callable,
) -> UUID:
    """Commit and verify admission, then commit and verify protected start."""
    if not callable(session_factory):
        raise ValueError("A callable session factory is required.")

    if not isinstance(project_id, UUID):
        raise ValueError("Invalid coordinator project identity.")

    if not callable(stage_admission):
        raise ValueError("A callable admission stage is required.")

    if not callable(stage_start_factory):
        raise ValueError("A callable start-stage factory is required.")

    execution_id = commit_and_verify_protected_admission(
        session_factory=session_factory,
        project_id=project_id,
        stage_admission=stage_admission,
    )

    if not isinstance(execution_id, UUID):
        raise ValueError(
            "Protected admission returned an invalid execution identity."
        )

    stage_start = stage_start_factory(execution_id)

    if not callable(stage_start):
        raise ValueError(
            "Protected start factory must return a callable stage."
        )

    started_id = commit_and_verify_protected_start(
        session_factory=session_factory,
        project_id=project_id,
        execution_id=execution_id,
        stage_start=stage_start,
    )

    if not isinstance(started_id, UUID) or started_id != execution_id:
        raise ValueError(
            "Protected coordinator execution identity mismatch."
        )

    return execution_id
