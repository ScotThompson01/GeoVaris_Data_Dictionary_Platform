"""Tests for internal Phase 5E atomic admission staging.

The staging service must not commit, execute source queries,
or authorize runtime execution.
"""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.models.data_quality_execution_capacity_reservation import (
    DataQualityExecutionCapacityReservation,
)
from app.models.data_quality_workload_ownership import (
    DataQualityWorkloadOwnership,
)
from app.services import data_quality_execution_admission_staging as staging


def prepared_fixture():
    project_id = uuid4()
    source_id = uuid4()
    object_id = uuid4()
    field_id = uuid4()
    rule_id = uuid4()

    prepared = {
        "rule": SimpleNamespace(id=rule_id, data_field_id=field_id),
        "version": SimpleNamespace(id=uuid4(), rule_id=rule_id),
        "field": SimpleNamespace(
            id=field_id, source_object_id=object_id
        ),
        "source_object": SimpleNamespace(
            id=object_id, data_source_id=source_id
        ),
        "source": SimpleNamespace(
            id=source_id, project_id=project_id
        ),
    }
    return prepared, project_id


@pytest.mark.parametrize(
    "broken_link",
    [
        "rule_field",
        "version_rule",
        "field_object",
        "object_source",
        "source_project",
    ],
)
def test_inconsistent_identity_rejected_before_database_access(broken_link):
    prepared, project_id = prepared_fixture()

    if broken_link == "rule_field":
        prepared["rule"].data_field_id = uuid4()
    elif broken_link == "version_rule":
        prepared["version"].rule_id = uuid4()
    elif broken_link == "field_object":
        prepared["field"].source_object_id = uuid4()
    elif broken_link == "object_source":
        prepared["source_object"].data_source_id = uuid4()
    else:
        prepared["source"].project_id = uuid4()

    db = Mock()

    with pytest.raises(ValueError):
        staging.stage_protected_execution_records(
            db,
            prepared=prepared,
            project_id=project_id,
            actor_user_id=uuid4(),
            installation_limit=2,
        )

    assert db.mock_calls == []


def test_stages_execution_ownership_and_two_reservations_without_commit(
    monkeypatch,
):
    prepared, project_id = prepared_fixture()
    actor_id = uuid4()
    execution = SimpleNamespace(
        id=uuid4(),
        rule_id=prepared["rule"].id,
        project_id=project_id,
    )
    installation = SimpleNamespace(
        id=uuid4(), scope_type="installation", data_source_id=None
    )
    source_control = SimpleNamespace(
        id=uuid4(),
        scope_type="source",
        data_source_id=prepared["source"].id,
    )

    capacity_check = Mock(
        return_value=(installation, source_control)
    )
    pending_stage = Mock(return_value=execution)

    monkeypatch.setattr(
        staging, "require_locked_execution_capacity", capacity_check
    )
    monkeypatch.setattr(
        staging, "stage_pending_execution", pending_stage
    )

    db = Mock()

    result = staging.stage_protected_execution_records(
        db,
        prepared=prepared,
        project_id=project_id,
        actor_user_id=actor_id,
        installation_limit=2,
    )

    capacity_check.assert_called_once_with(
        db,
        data_source_id=prepared["source"].id,
        installation_limit=2,
    )
    pending_stage.assert_called_once_with(
        db,
        prepared=prepared,
        project_id=project_id,
        actor_user_id=actor_id,
    )

    assert result["execution"] is execution

    staged = [call.args[0] for call in db.add.call_args_list]
    ownership = [
        item for item in staged
        if isinstance(item, DataQualityWorkloadOwnership)
    ]
    reservations = [
        item for item in staged
        if isinstance(item, DataQualityExecutionCapacityReservation)
    ]

    assert len(ownership) == 1
    assert len(reservations) == 2

    workload = ownership[0]
    assert workload.execution_id == execution.id
    assert workload.project_id == project_id
    assert workload.rule_id == prepared["rule"].id
    assert workload.data_field_id == prepared["field"].id
    assert workload.source_object_id == prepared["source_object"].id
    assert workload.data_source_id == prepared["source"].id
    assert workload.ownership_state == "reserved"

    assert {item.reservation_scope for item in reservations} == {
        "installation", "source"
    }
    assert all(item.ownership_id == workload.id for item in reservations)
    assert all(item.reservation_state == "reserved" for item in reservations)
    assert all(
        item.ownership_data_source_id == prepared["source"].id
        for item in reservations
    )
    assert {
        (item.reservation_scope, item.capacity_control_id, item.data_source_id)
        for item in reservations
    } == {
        ("installation", installation.id, None),
        ("source", source_control.id, prepared["source"].id),
    }

    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.execute.assert_not_called()


def test_pending_staging_failure_does_not_create_ownership(
    monkeypatch,
):
    prepared, project_id = prepared_fixture()
    installation = SimpleNamespace(
        id=uuid4(), scope_type="installation", data_source_id=None
    )
    source_control = SimpleNamespace(
        id=uuid4(),
        scope_type="source",
        data_source_id=prepared["source"].id,
    )

    monkeypatch.setattr(
        staging,
        "require_locked_execution_capacity",
        Mock(return_value=(installation, source_control)),
    )
    monkeypatch.setattr(
        staging,
        "stage_pending_execution",
        Mock(side_effect=RuntimeError("synthetic staging failure")),
    )

    db = Mock()

    with pytest.raises(RuntimeError, match="synthetic staging failure"):
        staging.stage_protected_execution_records(
            db,
            prepared=prepared,
            project_id=project_id,
            actor_user_id=uuid4(),
            installation_limit=2,
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()
