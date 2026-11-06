"""Internal-only adapter for persisted administrator release.

Not connected to runtime or production-authorized. The caller must
independently establish an authenticated actor identity and own the
transaction commit or rollback.

All release locks, evidence checks, reviewer checks, and state changes
are performed by the trusted transaction implementation.
"""

from uuid import UUID

from app.services.data_quality_execution_release_transaction import (
    stage_locked_persisted_admin_release,
)


def stage_persisted_admin_resolution(
    db,
    *,
    project_id: UUID,
    ownership_id: UUID,
    data_source_id: UUID,
    evidence_id: UUID,
    trusted_actor_user_id: UUID,
    reason: str,
    evidence_reference: str,
) -> None:
    """Delegate to the mandatory persisted-evidence release transaction."""
    stage_locked_persisted_admin_release(
        db,
        project_id=project_id,
        ownership_id=ownership_id,
        data_source_id=data_source_id,
        evidence_id=evidence_id,
        trusted_actor_user_id=trusted_actor_user_id,
        reason=reason,
        evidence_reference=evidence_reference,
    )
