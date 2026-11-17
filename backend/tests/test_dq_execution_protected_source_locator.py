"""Offline tests for the protected-start source locator.

The locator selects a capacity-lock target, not an authorization decision.
"""

from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.services.data_quality_execution_protected_start import (
    _locate_protected_execution_source,
)


def test_locator_uses_project_and_execution_filters_without_row_lock():
    project_id = uuid4()
    execution_id = uuid4()
    source_id = uuid4()

    db = Mock()
    db.scalar.return_value = source_id

    result = _locate_protected_execution_source(
        db,
        project_id=project_id,
        execution_id=execution_id,
    )

    assert result == source_id
    db.scalar.assert_called_once()

    statement = db.scalar.call_args.args[0]
    assert statement._for_update_arg is None

    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)

    assert "data_quality_workload_ownership" in sql
    assert "data_source_id" in sql
    assert "execution_id" in sql
    assert "project_id" in sql
    assert "FOR UPDATE" not in sql.upper()

    assert project_id in compiled.params.values()
    assert execution_id in compiled.params.values()

    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.add.assert_not_called()


@pytest.mark.parametrize(
    "invalid_field",
    ["project_id", "execution_id"],
)
def test_locator_rejects_invalid_identity_before_query(invalid_field):
    db = Mock()

    identities = {
        "project_id": uuid4(),
        "execution_id": uuid4(),
    }
    identities[invalid_field] = "invalid-uuid"

    with pytest.raises(ValueError, match="Invalid"):
        _locate_protected_execution_source(db, **identities)

    db.scalar.assert_not_called()


@pytest.mark.parametrize(
    "source_value",
    [None, "invalid-source", 123],
)
def test_locator_rejects_missing_or_invalid_source(source_value):
    db = Mock()
    db.scalar.return_value = source_value

    with pytest.raises(ValueError, match="source is unavailable"):
        _locate_protected_execution_source(
            db,
            project_id=uuid4(),
            execution_id=uuid4(),
        )

    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
