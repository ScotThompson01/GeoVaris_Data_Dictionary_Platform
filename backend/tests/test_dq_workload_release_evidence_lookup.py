"""Isolated SQL and fail-closed checks for persisted evidence lookup."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.services.data_quality_workload_release_evidence_lookup import (
    load_consistent_release_evidence as load,
)

NOW = datetime(2026, 11, 4, tzinfo=timezone.utc)


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.statements = []

    def scalar(self, statement):
        assert statement._for_update_arg is not None
        self.statements.append(statement)
        return self.responses.pop(0)


def scenario(admin=False):
    project_id = uuid4()
    source_id = uuid4()
    ownership_id = uuid4()
    evidence_id = uuid4()
    actor_id = uuid4()

    ownership = SimpleNamespace(
        id=ownership_id,
        project_id=project_id,
        data_source_id=source_id,
        ownership_state="unresolved",
    )

    grant = (
        SimpleNamespace(
            id=uuid4(),
            project_id=project_id,
            user_id=actor_id,
            granted_by_user_id=uuid4(),
            created_at=NOW - timedelta(days=1),
            revoked_at=None,
        )
        if admin else None
    )

    evidence = SimpleNamespace(
        id=evidence_id,
        ownership_id=ownership_id,
        project_id=project_id,
        data_source_id=source_id,
        actor_user_id=actor_id,
        resolution_grant_id=grant.id if grant else None,
        evidence_type=(
            "authorized_admin_resolution"
            if admin else "verified_source_termination"
        ),
        evidence_status="confirmed",
        reason="Documented resolution",
        evidence_reference="local-evidence-001",
        verified_by_user_id=uuid4(),
        created_at=NOW,
        verified_at=NOW + timedelta(minutes=1),
    )

    kwargs = dict(
        evidence_id=evidence_id,
        ownership_id=ownership_id,
        project_id=project_id,
        data_source_id=source_id,
    )

    responses = (
        [ownership, evidence, uuid4(), grant]
        if admin else [ownership, evidence]
    )

    return FakeSession(responses), evidence, ownership, grant, kwargs


@pytest.mark.parametrize("admin", [False, True])
def test_scoped_lookup_returns_consistent_evidence(admin):
    db, evidence, ownership, grant, kwargs = scenario(admin)

    assert load(db, **kwargs) is evidence
    assert len(db.statements) == (4 if admin else 2)


@pytest.mark.parametrize(
    "field",
    ["evidence_id", "ownership_id", "project_id", "data_source_id"],
)
def test_invalid_input_rejected_before_read(field):
    db, evidence, ownership, grant, kwargs = scenario()
    kwargs[field] = "invalid"

    with pytest.raises(ValueError, match="Invalid"):
        load(db, **kwargs)

    assert db.statements == []


def test_missing_ownership_fails_closed():
    db, evidence, ownership, grant, kwargs = scenario()
    db.responses[0] = None

    with pytest.raises(ValueError, match="ownership not found"):
        load(db, **kwargs)

    assert len(db.statements) == 1


def test_missing_evidence_fails_closed():
    db, evidence, ownership, grant, kwargs = scenario()
    db.responses[1] = None

    with pytest.raises(ValueError, match="evidence not found"):
        load(db, **kwargs)

    assert len(db.statements) == 2


def test_unconfirmed_evidence_rejected():
    db, evidence, ownership, grant, kwargs = scenario()
    evidence.evidence_status = "recorded"

    with pytest.raises(ValueError, match="not been confirmed"):
        load(db, **kwargs)


def test_cross_project_evidence_rejected():
    db, evidence, ownership, grant, kwargs = scenario()
    evidence.project_id = uuid4()

    with pytest.raises(ValueError, match="identity mismatch"):
        load(db, **kwargs)


def test_missing_admin_membership_rejected():
    db, evidence, ownership, grant, kwargs = scenario(admin=True)
    db.responses[2] = None

    with pytest.raises(ValueError, match="membership"):
        load(db, **kwargs)

    assert len(db.statements) == 3


def test_missing_admin_grant_rejected():
    db, evidence, ownership, grant, kwargs = scenario(admin=True)
    db.responses[3] = None

    with pytest.raises(ValueError, match="Active"):
        load(db, **kwargs)

    assert len(db.statements) == 4


def test_revoked_admin_grant_rejected():
    db, evidence, ownership, grant, kwargs = scenario(admin=True)
    grant.revoked_at = NOW

    with pytest.raises(ValueError, match="revoked"):
        load(db, **kwargs)


def test_admin_grant_for_other_user_rejected():
    db, evidence, ownership, grant, kwargs = scenario(admin=True)
    grant.user_id = uuid4()

    with pytest.raises(ValueError, match="identity mismatch"):
        load(db, **kwargs)


def test_lookup_queries_are_scoped_and_locked():
    db, evidence, ownership, grant, kwargs = scenario(admin=True)

    load(db, **kwargs)

    sql = [
        str(statement.compile(dialect=postgresql.dialect()))
        for statement in db.statements
    ]

    assert "data_quality_workload_ownership" in sql[0]
    assert "data_quality_workload_release_evidence" in sql[1]
    assert "project_access" in sql[2]
    assert "data_quality_workload_resolution_grants" in sql[3]

    for statement in db.statements:
        assert statement._for_update_arg is not None

    assert "ownership_id" in sql[1]
    assert "project_id" in sql[1]
    assert "data_source_id" in sql[1]
    assert "revoked_at IS NULL" in sql[3]

    compiled_evidence = db.statements[1].compile(
        dialect=postgresql.dialect()
    )
    for value in kwargs.values():
        assert value in compiled_evidence.params.values()


def test_lookup_never_commits_or_flushes():
    db, evidence, ownership, grant, kwargs = scenario(admin=True)

    load(db, **kwargs)

    assert not hasattr(db, "commit")
    assert not hasattr(db, "flush")
