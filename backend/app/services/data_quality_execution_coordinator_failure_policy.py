"""Fail-closed failure classification for protected Phase 5E execution.

Internal policy only. NOT connected to admission, API routes, worker
execution, source measurements, or recovery transactions.

Commit evidence must be independently verified by the caller.
An ambiguous commit outcome must never be represented as False.
This policy cannot release reservations or establish source shutdown.
"""

_ALLOWED_STATES = {
    ("admission", False, False):
        "rollback_uncommitted_admission",
    ("before_running", True, False):
        "manual_review_required",
    ("before_measurement", True, True):
        "manual_review_required",
    ("measurement", True, True):
        "manual_review_required",
    ("outcome_recording", True, True):
        "manual_review_required",
    ("outcome_committed", True, True):
        "manual_review_required",
    # An unknown commit outcome is not evidence of rollback.
    # Never start source work or release capacity on this evidence.
    ("admission", None, False):
        "manual_review_required",
    ("before_running", None, False):
        "manual_review_required",
    ("before_running", True, None):
        "manual_review_required",
    ("before_measurement", True, None):
        "manual_review_required",
    ("measurement", True, None):
        "manual_review_required",
    ("outcome_recording", True, None):
        "manual_review_required",
}


def assess_coordinator_failure(
    *,
    phase: str,
    admission_committed: bool,
    running_committed: bool,
) -> str:
    """Classify verified failure evidence without side effects.

    ``rollback_uncommitted_admission`` requires proof that admission did
    not commit. It is not a capacity-release authorization.

    ``manual_review_required`` preserves protections for subsequent
    independently authorized recovery assessment.
    """
    if not isinstance(phase, str):
        raise ValueError("Invalid coordinator phase.")

    if (
        admission_committed is not None
        and type(admission_committed) is not bool
    ) or (
        running_committed is not None
        and type(running_committed) is not bool
    ):
        raise ValueError(
            "Coordinator transaction evidence must be boolean or None."
        )

    outcome = _ALLOWED_STATES.get(
        (phase, admission_committed, running_committed)
    )

    if outcome is None:
        raise ValueError(
            "Invalid or inconsistent coordinator transaction state."
        )

    return outcome
