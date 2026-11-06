"""Fail-closed preliminary reviewer authority checks."""

from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.services.data_quality_release_reviewer_authorization import (
    require_release_reviewer_authority,
)


class FakeSession:
    def __init__(self, reviewer, membership):
        self.responses = [reviewer, membership]
        self.statements = []

    def scalar(self, statement):
        assert statement._for_update_arg is not None
        self.statements.append(statement)
        return self.responses.pop(0)


def test_authorized_reviewer_requires_both_current_records():
    reviewer_id, project_id = uuid4(), uuid4()
    db = FakeSession(object(), uuid4())

    require_release_reviewer_authority(
        db,
        reviewer_user_id=reviewer_id,
        project_id=project_id,
    )

    assert len(db.statements) == 2
    queries = [
        statement.compile(dialect=postgresql.dialect())
        for statement in db.statements
    ]
    assert "users" in str(queries[0])
    assert "is_active IS true" in str(queries[0])
    assert "is_installation_admin IS true" in str(queries[0])
    assert "project_access" in str(queries[1])
    assert reviewer_id in queries[0].params.values()
    assert reviewer_id in queries[1].params.values()
    assert project_id in queries[1].params.values()


def test_missing_active_administrator_rejected():
    db = FakeSession(None, uuid4())

    with pytest.raises(ValueError, match="Active installation"):
        require_release_reviewer_authority(
            db,
            reviewer_user_id=uuid4(),
            project_id=uuid4(),
        )

    assert len(db.statements) == 1


def test_missing_reviewer_membership_rejected():
    db = FakeSession(object(), None)

    with pytest.raises(ValueError, match="Reviewer project membership"):
        require_release_reviewer_authority(
            db,
            reviewer_user_id=uuid4(),
            project_id=uuid4(),
        )

    assert len(db.statements) == 2


@pytest.mark.parametrize("field", ["reviewer_user_id", "project_id"])
def test_invalid_identity_rejected_without_database_access(field):
    kwargs = {
        "reviewer_user_id": uuid4(),
        "project_id": uuid4(),
    }
    kwargs[field] = "invalid"
    db = FakeSession(object(), uuid4())

    with pytest.raises(ValueError, match="Invalid"):
        require_release_reviewer_authority(db, **kwargs)

    assert db.statements == []
