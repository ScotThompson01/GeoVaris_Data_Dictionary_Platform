"""Lock existing Phase 5E capacity controls without reserving capacity.

Internal-only transaction helper. Not connected to runtime admission.
The caller owns commit/rollback and must retain locks until transaction end.

Global lock order: installation capacity control, then source capacity control.
This helper performs no source I/O, counting, insertion, or state mutation.
"""

from uuid import UUID

from sqlalchemy import select

from app.models.data_quality_execution_capacity_control import (
    DataQualityExecutionCapacityControl as CapacityControl,
)


def lock_existing_execution_capacity_controls(
    db,
    *,
    data_source_id: UUID,
) -> tuple[CapacityControl, CapacityControl]:
    """Lock and validate existing installation/source capacity controls."""
    if not isinstance(data_source_id, UUID):
        raise ValueError("Invalid data source identity.")

    installation = db.scalar(
        select(CapacityControl)
        .where(CapacityControl.scope_type == "installation")
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if (
        installation is None
        or installation.scope_type != "installation"
        or installation.data_source_id is not None
        or type(installation.max_concurrent) is not int
        or installation.max_concurrent < 1
    ):
        raise ValueError(
            "Installation capacity control is unavailable or inconsistent."
        )

    source = db.scalar(
        select(CapacityControl)
        .where(
            CapacityControl.scope_type == "source",
            CapacityControl.data_source_id == data_source_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if (
        source is None
        or source.scope_type != "source"
        or source.data_source_id != data_source_id
        or type(source.max_concurrent) is not int
        or source.max_concurrent < 1
    ):
        raise ValueError(
            "Source capacity control is unavailable or inconsistent."
        )

    return installation, source