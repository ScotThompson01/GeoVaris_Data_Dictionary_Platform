"""Internal Phase 5E protected execution-admission staging.

NOT connected to API routes or source measurements.
NOT production-authorized.

Admission remains fail-closed until persistent capacity locking,
ownership, reservations, and recovery safeguards are implemented.

The caller will own commit/rollback when transaction staging is added.
"""

from uuid import UUID

from app.core.config import settings
from app.services.data_quality_execution_capacity_policy import (
    ExecutionCapacityPolicyError,
    require_execution_capacity_configuration,
)


def stage_protected_execution_admission(
    db,
    *,
    prepared: dict,
    project_id: UUID,
    actor_user_id: UUID,
):
    """Reject execution unless protected admission is fully implemented.

    Configuration is checked before any database interaction.
    Merely enabling the setting cannot authorize source execution.
    """
    require_execution_capacity_configuration(settings)

    raise ExecutionCapacityPolicyError(
        "Protected Data Quality execution admission "
        "is not yet implemented."
    )
