"""Tests for read-only Phase 5E protected workload inventory.

An active reservation is not evidence of a crashed or stopped workload.
Inventory must not change state or authorize capacity release.
"""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.services.data_quality_execution_recovery_inventory import (
    list_project_protected_workload_candidates,
)


def test_inventory_is_project_scoped_and_includes_both_active_states():
    project_id = uuid4()
    rows = [
        SimpleNamespace(
            id=uuid4(),
            project_id=project_id,
            ownership_state="reserved",
        ),
        SimpleNamespace(
            id=uuid4(),
            project_id=project_id,
            ownership_state="unresolved",
        ),
    ]

    db = Mock()
    db.scalars.return_value.all.return_value = rows

    result = list_project_protected_workload_candidates(
        db, project_id=project_id
    )

    assert result == rows
    db.scalars.assert_called_once()

    statement = db.scalars.call_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    values = list(compiled.params.values())

    assert "data_quality_workload_ownership" in sql
    assert "project_id" in sql
    assert "ownership_state" in sql
    assert " IN " in sql.upper()
    assert project_id in values
    assert any(
        isinstance(value, (list, tuple))
        and set(value) == {"reserved", "unresolved"}
        for value in values
    )
    assert not any(
        isinstance(value, (list, tuple))
        and "released" in value
        for value in values
    )

    # Do not filter by execution status: a terminal status does not
    # prove that the underlying source workload has stopped.
    assert "data_quality_rule_executions" not in sql

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.execute.assert_not_called()


@pytest.mark.parametrize("project_id", [
    None,
    "",
    "not-a-uuid",
    123,
    True,
])
def test_invalid_project_identity_fails_before_database_access(project_id):
    db = Mock()

    with pytest.raises(ValueError, match="project"):
        list_project_protected_workload_candidates(
            db, project_id=project_id
        )

    assert db.mock_calls == []


def test_empty_project_inventory_is_not_an_interruption_signal():
    db = Mock()
    db.scalars.return_value.all.return_value = []

    result = list_project_protected_workload_candidates(
        db, project_id=uuid4()
    )

    assert result == []
    db.commit.assert_not_called()
    db.add.assert_not_called()
