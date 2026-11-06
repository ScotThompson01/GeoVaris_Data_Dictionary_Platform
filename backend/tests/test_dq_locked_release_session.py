"""Fail-closed tests for Phase 5E locked session validation."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.services.auth_sessions import _token_hash
from app.services.data_quality_locked_release_session import (
    require_locked_release_session,
)


TOKEN = "release-test-session-token"


class FakeSession:
    def __init__(self, record):
        self.record = record
        self.statements = []

    def scalar(self, statement):
        self.statements.append(statement)
        return self.record


def valid_record(actor_id):
    return SimpleNamespace(
        user_id=actor_id,
        revoked_at=None,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


def test_valid_session_uses_locked_hashed_token_query():
    actor_id = uuid4()
    db = FakeSession(valid_record(actor_id))

    require_locked_release_session(
        db,
        session_token=TOKEN,
        expected_actor_user_id=actor_id,
    )

    assert len(db.statements) == 1
    statement = db.statements[0]

    assert statement._for_update_arg is not None
    assert statement.get_execution_options().get("populate_existing") is True

    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)

    assert "auth_sessions" in sql
    assert "token_hash" in sql
    assert "user_id" in sql
    assert "revoked_at IS NULL" in sql
    assert "expires_at >" in sql
    assert "FOR UPDATE" in sql

    assert _token_hash(TOKEN) in compiled.params.values()
    assert actor_id in compiled.params.values()
    assert TOKEN not in compiled.params.values()
    assert TOKEN not in sql


@pytest.mark.parametrize(
    "record_type",
    ["missing", "wrong_actor", "revoked", "expired"],
)
def test_invalid_session_record_cannot_authorize_release(record_type):
    actor_id = uuid4()
    record = valid_record(actor_id)

    if record_type == "missing":
        record = None
    elif record_type == "wrong_actor":
        record.user_id = uuid4()
    elif record_type == "revoked":
        record.revoked_at = datetime.now(timezone.utc)
    elif record_type == "expired":
        record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    db = FakeSession(record)

    with pytest.raises(PermissionError, match="authenticated release session"):
        require_locked_release_session(
            db,
            session_token=TOKEN,
            expected_actor_user_id=actor_id,
        )

    assert len(db.statements) == 1


@pytest.mark.parametrize(
    "token",
    [None, "", " ", " leading", "trailing ", "two tokens", "tab\tvalue"],
)
def test_invalid_token_is_rejected_before_database_access(token):
    db = FakeSession(None)

    with pytest.raises(PermissionError, match="authenticated release session"):
        require_locked_release_session(
            db,
            session_token=token,
            expected_actor_user_id=uuid4(),
        )

    assert db.statements == []


@pytest.mark.parametrize(
    "actor_id",
    [None, "claimed-user-id", 123],
)
def test_invalid_actor_is_rejected_before_database_access(actor_id):
    db = FakeSession(None)

    with pytest.raises(PermissionError, match="authenticated release session"):
        require_locked_release_session(
            db,
            session_token=TOKEN,
            expected_actor_user_id=actor_id,
        )

    assert db.statements == []
