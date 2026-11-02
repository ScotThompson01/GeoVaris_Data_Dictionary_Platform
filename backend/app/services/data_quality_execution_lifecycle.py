"""Proposed Data Quality execution lifecycle transition policy.

Phase 5E foundation. The transition matrix is an implementation proposal
pending design review, not a newly approved governance policy.

This module does not perform I/O, persist state, cancel source workloads,
or release execution safety locks.
"""

from enum import Enum


class ExecutionStatus(str, Enum):
    """Execution statuses required by the approved Phase 5 specification."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INCOMPLETE = "incomplete"
    STATUS_UNCERTAIN = "status_uncertain"
    CANCELLED = "cancelled"


# Conservative initial transitions.
# Uncertain workload resolution requires separate safety verification.
_ALLOWED_TRANSITIONS = {
    ExecutionStatus.PENDING: frozenset({
        ExecutionStatus.RUNNING,
        ExecutionStatus.CANCELLED,
    }),
    ExecutionStatus.RUNNING: frozenset({
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.INCOMPLETE,
        ExecutionStatus.STATUS_UNCERTAIN,
    }),
    ExecutionStatus.SUCCEEDED: frozenset(),
    ExecutionStatus.FAILED: frozenset(),
    ExecutionStatus.INCOMPLETE: frozenset(),
    ExecutionStatus.STATUS_UNCERTAIN: frozenset(),
    ExecutionStatus.CANCELLED: frozenset(),
}


def validate_execution_transition(
    current: ExecutionStatus,
    next_status: ExecutionStatus,
) -> None:
    """Reject invalid transitions without changing execution state.

    Unknown values and repeated transitions are rejected.
    """

    if not isinstance(current, ExecutionStatus):
        raise ValueError("Unknown current execution status.")

    if not isinstance(next_status, ExecutionStatus):
        raise ValueError("Unknown requested execution status.")

    if next_status not in _ALLOWED_TRANSITIONS[current]:
        raise ValueError(
            f"Execution transition from {current.value} "
            f"to {next_status.value} is not permitted."
        )
