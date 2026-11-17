"""Offline tests for internal project-scoped execution row locking.

No runtime admission, source access, or database connection is required.
"""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.services.data_quality_execution_persistence import (
    lock_existing_project_execution,
)


def test_locks_execution_with_project_scoped_filters():
    project_id = uuid4()
    execution_id = uuid4()
    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
    )
    db = Mock()
    db.scalar.return_value = execution

    result = lock_existing_project_execution(
        db,
        project_id=project_id,
        execution_id=execution_id,
    )

    assert result is execution
    db.scalar.assert_called_once()

    statement = db.scalar.call_args.args[0]
    assert statement._for_update_arg is not None

    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)

    assert "data_quality_rule_executions" in sql
    assert "project_id" in sql
    assert "data_quality_rule_executions.id" in sql
    assert project_id in compiled.params.values()
    assert execution_id in compiled.params.values()

    assert statement.get_execution_options()["populate_existing"] is True

    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.add.assert_not_called()


@pytest.mark.parametrize(
    "invalid_field",
    ["project_id", "execution_id"],
)
def test_rejects_invalid_identity_before_database_access(invalid_field):
    db = Mock()
    identities = {
        "project_id": uuid4(),
        "execution_id": uuid4(),
    }
    identities[invalid_field] = "not-a-uuid"

    with pytest.raises(ValueError, match="Invalid"):
        lock_existing_project_execution(db, **identities)

    db.scalar.assert_not_called()
    db.flush.assert_not_called()


def test_rejects_missing_execution():
    db = Mock()
    db.scalar.return_value = None

    with pytest.raises(ValueError, match="unavailable or inconsistent"):
        lock_existing_project_execution(
            db,
            project_id=uuid4(),
            execution_id=uuid4(),
        )

    db.flush.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "mismatch",
    ["execution_id", "project_id"],
)
def test_rejects_inconsistent_locked_execution(mismatch):
    project_id = uuid4()
    execution_id = uuid4()

    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
    )
    setattr(execution, "id" if mismatch == "execution_id" else mismatch, uuid4())

    db = Mock()
    db.scalar.return_value = execution

    with pytest.raises(ValueError, match="unavailable or inconsistent"):
        lock_existing_project_execution(
            db,
            project_id=project_id,
            execution_id=execution_id,
        )

    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_does_not_change_execution_state():
    project_id = uuid4()
    execution_id = uuid4()
    execution = SimpleNamespace(
        id=execution_id,
        project_id=project_id,
        status="pending",
        started_at=None,
    )
    db = Mock()
    db.scalar.return_value = execution

    result = lock_existing_project_execution(
        db,
        project_id=project_id,
        execution_id=execution_id,
    )

    assert result.status == "pending"
    assert result.started_at is None
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
