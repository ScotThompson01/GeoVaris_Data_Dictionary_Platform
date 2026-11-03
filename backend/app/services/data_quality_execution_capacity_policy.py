"""Fail-closed Phase 5E execution-capacity configuration policy.

Configuration validation alone never grants execution authorization.
Persistent workload reservations and source-specific limits are separate
requirements that must be enforced before source measurements begin.
"""


class ExecutionCapacityPolicyError(ValueError):
    """Raised when execution-capacity configuration is unsafe."""


def require_execution_capacity_configuration(settings) -> int:
    """Return an approved installation ceiling or reject execution admission.

    This function performs no I/O and does not acquire workload ownership.
    """
    if getattr(settings, "dq_execution_admission_enabled", False) is not True:
        raise ExecutionCapacityPolicyError(
            "Data Quality execution admission is disabled."
        )

    limit = getattr(settings, "dq_execution_max_concurrent", None)

    if type(limit) is not int or limit < 1:
        raise ExecutionCapacityPolicyError(
            "A positive integer installation execution limit is required."
        )

    return limit
