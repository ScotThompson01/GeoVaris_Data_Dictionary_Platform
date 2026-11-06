"""Fail-closed Phase 5E protected execution recovery assessment.

Internal policy only. NOT connected to API routes or runtime recovery.

This module makes no database queries, performs no source I/O,
changes no persistent state, and never releases capacity.

An interruption signal does not prove the source workload has stopped.
Manual verification and separately authorized release remain required.
"""

from uuid import UUID

from app.services.data_quality_execution_release_integrity import (
    validate_protected_workload,
)


KNOWN_EXECUTION_STATUSES = frozenset({
    "pending",
    "running",
    "succeeded",
    "failed",
    "incomplete",
    "status_uncertain",
    "cancelled",
})


def assess_protected_execution_recovery(
    *,
    execution,
    ownership,
    reservations,
    interruption_detected: bool,
) -> str:
    """Assess interruption conservatively without changing protection.

    Returns:
        manual_review_required: Explicit interruption detected.
        no_recovery_action: No interruption reported.

    Neither result authorizes source cancellation or capacity release.
    """
    if type(interruption_detected) is not bool:
        raise ValueError("A valid interruption signal is required.")

    if execution is None:
        raise ValueError("An execution record is required.")

    execution_id = getattr(execution, "id", None)

    if not isinstance(execution_id, UUID):
        raise ValueError("Invalid execution identity.")

    if getattr(execution, "status", None) not in KNOWN_EXECUTION_STATUSES:
        raise ValueError("Unknown execution status.")

    if (
        ownership is None
        or getattr(ownership, "execution_id", None) != execution_id
    ):
        raise ValueError("Execution and workload ownership identity mismatch.")

    validate_protected_workload(
        ownership=ownership,
        reservations=reservations,
    )

    if interruption_detected:
        return "manual_review_required"

    return "no_recovery_action"
