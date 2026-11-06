"""Unit tests for Phase 5E transactional capacity checks.

No source connections or real databases are used.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.data_quality_execution_admission_capacity import (
    require_locked_execution_capacity,
)


class FakeSession:
    def __init__(self, installation, source, counts):
        self.rows = [installation, source]
        self.counts = list(counts)
        self.statements = []
        self.count_statements = []

    def scalar(self, statement):
        self.statements.append(statement)
        return self.rows.pop(0)

    def execute(self, statement):
        self.count_statements.append(statement)
        return SimpleNamespace(scalar_one=lambda: self.counts.pop(0))


def controls(source_id, installation_limit=2, source_limit=1):
    installation = SimpleNamespace(
        id=uuid4(),
        scope_type="installation",
        data_source_id=None,
        max_concurrent=installation_limit,
    )
    source = SimpleNamespace(
        id=uuid4(),
        scope_type="source",
        data_source_id=source_id,
        max_concurrent=source_limit,
    )
    return installation, source


def test_capacity_checks_lock_installation_then_source():
    source_id = uuid4()
    installation, source = controls(source_id)
    db = FakeSession(installation, source, [0, 0])

    result = require_locked_execution_capacity(
        db, data_source_id=source_id, installation_limit=2
    )

    assert result == (installation, source)
    assert len(db.statements) == 2
    assert all(s._for_update_arg is not None for s in db.statements)
    assert len(db.count_statements) == 2
    db_queries = [str(s.compile()) for s in db.statements]
    assert "scope_type" in db_queries[0]
    assert "data_source_id" in db_queries[1]


@pytest.mark.parametrize("counts", [(2, 0), (1, 1), (3, 2)])
def test_exhausted_capacity_is_rejected(counts):
    source_id = uuid4()
    installation, source = controls(source_id)
    db = FakeSession(installation, source, counts)

    with pytest.raises(ValueError, match="capacity"):
        require_locked_execution_capacity(
            db, data_source_id=source_id, installation_limit=2
        )


def test_missing_source_control_fails_closed():
    source_id = uuid4()
    installation, _ = controls(source_id)
    db = FakeSession(installation, None, [])

    with pytest.raises(ValueError, match="Source capacity"):
        require_locked_execution_capacity(
            db, data_source_id=source_id, installation_limit=2
        )

    assert db.count_statements == []


def test_mismatched_source_control_fails_closed():
    source_id = uuid4()
    installation, wrong_source = controls(uuid4())
    db = FakeSession(installation, wrong_source, [])

    with pytest.raises(ValueError, match="Source capacity"):
        require_locked_execution_capacity(
            db, data_source_id=source_id, installation_limit=2
        )


def test_missing_installation_control_fails_closed():
    db = FakeSession(None, None, [])

    with pytest.raises(ValueError, match="Installation capacity"):
        require_locked_execution_capacity(
            db, data_source_id=uuid4(), installation_limit=2
        )

    assert len(db.statements) == 1
    assert db.count_statements == []


def test_invalid_source_identity_rejected_without_queries():
    db = FakeSession(None, None, [])

    with pytest.raises(ValueError, match="source"):
        require_locked_execution_capacity(
            db, data_source_id="not-a-uuid", installation_limit=2
        )

    assert db.statements == []
    assert db.count_statements == []



def test_capacity_queries_include_reserved_and_unresolved_states():
    from sqlalchemy.dialects import postgresql

    source_id = uuid4()
    installation, source = controls(
        source_id,
        installation_limit=3,
        source_limit=2,
    )
    db = FakeSession(installation, source, [1, 1])

    require_locked_execution_capacity(
        db,
        data_source_id=source_id,
        installation_limit=3,
    )

    assert len(db.count_statements) == 2

    for statement, expected_control, expected_scope in (
        (db.count_statements[0], installation, "installation"),
        (db.count_statements[1], source, "source"),
    ):
        compiled = statement.compile(
            dialect=postgresql.dialect()
        )
        sql = str(compiled)
        parameters = compiled.params

        assert "count(" in sql.lower()
        assert "data_quality_execution_capacity_reservations" in sql
        assert "capacity_control_id" in sql
        assert "reservation_scope" in sql
        assert "reservation_state" in sql
        assert " IN " in sql.upper()

        values = list(parameters.values())

        assert expected_control.id in values
        assert expected_scope in values

        state_values = [
            item
            for item in values
            if isinstance(item, (tuple, list))
            and set(item) == {"reserved", "unresolved"}
        ]

        assert len(state_values) == 1, (
            "Both reserved and unresolved reservations "
            "must count against capacity."
        )

        assert "released" not in state_values[0]
