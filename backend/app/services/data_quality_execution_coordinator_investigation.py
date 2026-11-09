"""Side-effect-free ambiguous-commit investigation assessment.

Internal Phase 5E policy only. NOT connected to API routes, runtime
admission, workers, database connections, or client-source measurement.

An observation of 'not_found' does not prove that an uncertain
transaction rolled back. A later or more reliable investigation
may produce different evidence.

This assessment does not authorize retries, source measurement,
capacity release, or any recovery transaction.
"""

from typing import Literal, TypedDict

from app.services.data_quality_execution_coordinator_failure_policy import (
    assess_coordinator_failure,
)


ExecutionObservation = Literal["found", "not_found", "unavailable"]


class AmbiguousCommitAssessment(TypedDict):
    disposition: str
    execution_observation: ExecutionObservation
    automatic_retry_allowed: bool
    capacity_release_allowed: bool
    source_measurement_allowed: bool


def assess_ambiguous_commit_investigation(
    *,
    phase: str,
    admission_committed: bool | None,
    running_committed: bool | None,
    execution_observation: ExecutionObservation,
) -> AmbiguousCommitAssessment:
    """Classify uncertain commit evidence without any side effects."""
    if (
        not isinstance(execution_observation, str)
        or execution_observation
        not in ("found", "not_found", "unavailable")
    ):
        raise ValueError("Invalid execution investigation observation.")

    # This service is specifically for uncertain commit outcomes.
    # Verified False is not equivalent to unknown, and verified True
    # is not an ambiguous outcome.
    if (
        type(admission_committed) is not type(None)
        and type(running_committed) is not type(None)
    ):
        raise ValueError(
            "Ambiguous-commit investigation requires unknown commit evidence."
        )

    disposition = assess_coordinator_failure(
        phase=phase,
        admission_committed=admission_committed,
        running_committed=running_committed,
    )

    if disposition != "manual_review_required":
        raise ValueError(
            "Ambiguous commit must require manual review."
        )

    return {
        "disposition": "manual_review_required",
        "execution_observation": execution_observation,
        "automatic_retry_allowed": False,
        "capacity_release_allowed": False,
        "source_measurement_allowed": False,
    }
