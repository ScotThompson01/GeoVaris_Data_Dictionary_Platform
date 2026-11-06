"""Internal transactional staging for Phase 5E protected admission.

NOT connected to execution API routes or source measurements.
NOT production-authorized.

The caller must provide freshly authorized prepared metadata and own the
database transaction. On any error, the caller MUST roll back the entire
transaction; do not commit or continue using a partially staged transaction.

Capacity-control locks must be held until the caller commits or rolls back.
"""

from uuid import UUID, uuid4

from app.models.data_quality_execution_capacity_reservation import (
    DataQualityExecutionCapacityReservation,
)
from app.models.data_quality_workload_ownership import (
    DataQualityWorkloadOwnership,
)
from app.services.data_quality_execution_admission_capacity import (
    require_locked_execution_capacity,
)
from app.services.data_quality_execution_persistence import (
    stage_pending_execution,
)


def _require_prepared_identities(
    prepared: dict,
    *,
    project_id: UUID,
    actor_user_id: UUID,
) -> dict:
    """Validate cross-record identities before any database interaction."""
    if not isinstance(project_id, UUID):
        raise ValueError("Invalid project identity.")

    if not isinstance(actor_user_id, UUID):
        raise ValueError("Invalid actor identity.")

    if not isinstance(prepared, dict):
        raise ValueError("Invalid prepared execution metadata.")

    keys = ("rule", "version", "field", "source_object", "source")
    records = {key: prepared.get(key) for key in keys}

    if any(record is None for record in records.values()):
        raise ValueError("Incomplete prepared execution metadata.")

    rule = records["rule"]
    version = records["version"]
    field = records["field"]
    source_object = records["source_object"]
    source = records["source"]

    identities = (
        rule.id,
        version.id,
        field.id,
        source_object.id,
        source.id,
    )

    if not all(isinstance(value, UUID) for value in identities):
        raise ValueError("Invalid prepared execution identity.")

    if version.rule_id != rule.id:
        raise ValueError("Rule version identity mismatch.")

    if rule.data_field_id != field.id:
        raise ValueError("Rule and data field identity mismatch.")

    if field.source_object_id != source_object.id:
        raise ValueError("Data field and source object identity mismatch.")

    if source_object.data_source_id != source.id:
        raise ValueError("Source object and data source identity mismatch.")

    if source.project_id != project_id:
        raise ValueError("Data source and project identity mismatch.")

    return records


def stage_protected_execution_records(
    db,
    *,
    prepared: dict,
    project_id: UUID,
    actor_user_id: UUID,
    installation_limit: int,
) -> dict:
    """Stage an execution, ownership, and both capacity reservations.

    No commit, rollback, source I/O, or runtime authorization occurs here.
    All records must be committed together by a trusted transaction owner.
    """
    records = _require_prepared_identities(
        prepared,
        project_id=project_id,
        actor_user_id=actor_user_id,
    )

    installation, source_control = require_locked_execution_capacity(
        db,
        data_source_id=records["source"].id,
        installation_limit=installation_limit,
    )

    if (
        not isinstance(getattr(installation, "id", None), UUID)
        or getattr(installation, "scope_type", None) != "installation"
        or getattr(installation, "data_source_id", None) is not None
        or not isinstance(getattr(source_control, "id", None), UUID)
        or getattr(source_control, "scope_type", None) != "source"
        or getattr(source_control, "data_source_id", None)
        != records["source"].id
    ):
        raise ValueError("Invalid locked execution capacity controls.")

    execution = stage_pending_execution(
        db,
        prepared=prepared,
        project_id=project_id,
        actor_user_id=actor_user_id,
    )

    if (
        not isinstance(getattr(execution, "id", None), UUID)
        or getattr(execution, "project_id", None) != project_id
        or getattr(execution, "rule_id", None) != records["rule"].id
    ):
        raise ValueError("Invalid staged execution identity.")

    # Explicit IDs permit reservation foreign keys to be established
    # without relying on a later database-generated default.
    ownership = DataQualityWorkloadOwnership(
        id=uuid4(),
        execution_id=execution.id,
        project_id=project_id,
        rule_id=records["rule"].id,
        data_field_id=records["field"].id,
        source_object_id=records["source_object"].id,
        data_source_id=records["source"].id,
        scope_type="full_object",
        ownership_state="reserved",
    )

    db.add(ownership)
    db.flush()

    installation_reservation = DataQualityExecutionCapacityReservation(
        id=uuid4(),
        ownership_id=ownership.id,
        capacity_control_id=installation.id,
        ownership_data_source_id=records["source"].id,
        data_source_id=None,
        reservation_scope="installation",
        reservation_state="reserved",
    )
    source_reservation = DataQualityExecutionCapacityReservation(
        id=uuid4(),
        ownership_id=ownership.id,
        capacity_control_id=source_control.id,
        ownership_data_source_id=records["source"].id,
        data_source_id=records["source"].id,
        reservation_scope="source",
        reservation_state="reserved",
    )

    db.add(installation_reservation)
    db.add(source_reservation)
    db.flush()

    return {
        "execution": execution,
        "ownership": ownership,
        "installation_reservation": installation_reservation,
        "source_reservation": source_reservation,
    }
