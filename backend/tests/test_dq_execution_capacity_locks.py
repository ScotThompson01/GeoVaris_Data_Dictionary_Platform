"""Offline tests for existing Phase 5E capacity-control locks."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.services.data_quality_execution_capacity_locks import (
    lock_existing_execution_capacity_controls,
)


class FakeSession:
    def __init__(self, installation, source):
        self.records = [installation, source]
        self.statements = []
        self.flush_count = 0

    def scalar(self, statement):
        self.statements.append(statement)
        return self.records.pop(0)

    def flush(self):
        self.flush_count += 1

    def commit(self):
        raise AssertionError("Helper must not commit.")

    def rollback(self):
        raise AssertionError("Helper must not roll back.")

    def execute(self, statement):
        raise AssertionError("Helper must not count reservations.")


def fixture():
    source_id = uuid4()

    installation = SimpleNamespace(
        id=uuid4(),
        scope_type="installation",
        data_source_id=None,
        max_concurrent=2,
    )

    source = SimpleNamespace(
        id=uuid4(),
        scope_type="source",
        data_source_id=source_id,
        max_concurrent=1,
    )

    return source_id, installation, source


def test_locks_installation_before_source_without_counting():
    source_id, installation, source = fixture()
    db = FakeSession(installation, source)

    result = lock_existing_execution_capacity_controls(
        db,
        data_source_id=source_id,
    )

    assert result == (installation, source)
    assert len(db.statements) == 2
    assert db.flush_count == 0

    for statement in db.statements:
        assert statement._for_update_arg is not None
        assert statement.get_execution_options().get(
            "populate_existing"
        ) is True

    compiled = [
        statement.compile(dialect=postgresql.dialect())
        for statement in db.statements
    ]

    sql = [str(statement) for statement in compiled]

    assert "data_quality_execution_capacity_controls" in sql[0]
    assert "scope_type" in sql[0]
    assert "data_source_id" in sql[1]
    assert source_id in compiled[1].params.values()


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_installation",
        "wrong_installation_scope",
        "installation_has_source",
        "invalid_installation_limit",
        "missing_source",
        "wrong_source_scope",
        "wrong_source_identity",
        "invalid_source_limit",
    ],
)
def test_invalid_controls_fail_closed(mutation):
    source_id, installation, source = fixture()

    if mutation == "missing_installation":
        installation = None
    elif mutation == "wrong_installation_scope":
        installation.scope_type = "source"
    elif mutation == "installation_has_source":
        installation.data_source_id = uuid4()
    elif mutation == "invalid_installation_limit":
        installation.max_concurrent = 0
    elif mutation == "missing_source":
        source = None
    elif mutation == "wrong_source_scope":
        source.scope_type = "installation"
    elif mutation == "wrong_source_identity":
        source.data_source_id = uuid4()
    elif mutation == "invalid_source_limit":
        source.max_concurrent = 0

    db = FakeSession(installation, source)

    with pytest.raises(ValueError):
        lock_existing_execution_capacity_controls(
            db,
            data_source_id=source_id,
        )

    assert db.flush_count == 0

    if mutation.startswith("missing_installation") or mutation in (
        "wrong_installation_scope",
        "installation_has_source",
        "invalid_installation_limit",
    ):
        assert len(db.statements) == 1
    else:
        assert len(db.statements) == 2


@pytest.mark.parametrize(
    "invalid_id",
    [None, "not-a-uuid", 123],
)
def test_invalid_source_identity_rejected_before_queries(invalid_id):
    source_id, installation, source = fixture()
    db = FakeSession(installation, source)

    with pytest.raises(ValueError, match="Invalid data source identity"):
        lock_existing_execution_capacity_controls(
            db,
            data_source_id=invalid_id,
        )

    assert db.statements == []
    assert db.flush_count == 0