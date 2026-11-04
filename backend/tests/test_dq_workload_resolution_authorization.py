"""Tests for the proposed dedicated workload resolution authorization."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import postgresql

from app.models.data_quality_workload_resolution_grant import (
    DataQualityWorkloadResolutionGrant,
)
from app.services.data_quality_workload_resolution_authorization import (
    require_workload_resolution_authority,
)


class FakeSession:
    def __init__(self, membership, grant):
        self.responses = [membership, grant]
        self.statements = []

    def scalar(self, statement):
        self.statements.append(statement)
        return self.responses.pop(0)


def test_active_dedicated_grant_allows_authorization():
    user_id, project_id = uuid4(), uuid4()
    db = FakeSession(uuid4(), uuid4())

    require_workload_resolution_authority(
        db, user_id=user_id, project_id=project_id
    )

    assert len(db.statements) == 2
    query = db.statements[1].compile(dialect=postgresql.dialect())
    sql = str(query)
    assert "data_quality_workload_resolution_grants" in sql
    assert "revoked_at IS NULL" in sql
    assert user_id in query.params.values()
    assert project_id in query.params.values()


def test_missing_project_membership_returns_404():
    db = FakeSession(None, uuid4())

    with pytest.raises(HTTPException) as exc:
        require_workload_resolution_authority(
            db, user_id=uuid4(), project_id=uuid4()
        )

    assert exc.value.status_code == 404
    assert len(db.statements) == 1


def test_missing_dedicated_grant_returns_403():
    db = FakeSession(uuid4(), None)

    with pytest.raises(HTTPException) as exc:
        require_workload_resolution_authority(
            db, user_id=uuid4(), project_id=uuid4()
        )

    assert exc.value.status_code == 403
    assert len(db.statements) == 2


@pytest.mark.parametrize("field", ["user_id", "project_id"])
def test_invalid_identity_fails_before_database_access(field):
    kwargs = {"user_id": uuid4(), "project_id": uuid4()}
    kwargs[field] = "invalid"
    db = FakeSession(uuid4(), uuid4())

    with pytest.raises(ValueError):
        require_workload_resolution_authority(db, **kwargs)

    assert db.statements == []


def test_grant_is_unique_per_project_and_user():
    table = DataQualityWorkloadResolutionGrant.__table__
    matches = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_dq_resolution_grant_project_user"
    ]
    assert len(matches) == 1
    assert [column.name for column in matches[0].columns] == [
        "project_id", "user_id"
    ]


def test_grant_requires_identified_grantor_and_supports_revocation():
    table = DataQualityWorkloadResolutionGrant.__table__
    assert table.c.granted_by_user_id.nullable is False
    assert table.c.revoked_at.nullable is True
    assert all(
        table.c[name].nullable is False
        for name in ("project_id", "user_id", "granted_by_user_id")
    )
