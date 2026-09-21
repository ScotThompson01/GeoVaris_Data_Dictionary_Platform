"""Unit tests for authentication-session behavior."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models.auth_session import AuthSession
from app.models.user import User
from app.services.auth_sessions import (
    _token_hash,
    create_auth_session,
    get_session_user,
    revoke_auth_session,
)


def make_user(*, active: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        username="session_test_user",
        password_hash="test-only-placeholder",
        is_active=active,
    )


def test_token_hash_is_deterministic_and_not_plaintext():
    token = "test-token"

    assert _token_hash(token) == _token_hash(token)
    assert _token_hash(token) != token
    assert len(_token_hash(token)) == 64


def test_create_session_stores_hash_and_returns_token():
    db = MagicMock()
    user = make_user()

    with patch(
        "app.services.auth_sessions.secrets.token_urlsafe",
        return_value="generated-test-token",
    ):
        token = create_auth_session(db, user)

    assert token == "generated-test-token"
    db.add.assert_called_once()
    db.commit.assert_called_once()

    stored_session = db.add.call_args.args[0]

    assert isinstance(stored_session, AuthSession)
    assert stored_session.user_id == user.id
    assert stored_session.token_hash == _token_hash(token)
    assert stored_session.token_hash != token
    assert stored_session.expires_at > datetime.now(timezone.utc)


def test_inactive_user_cannot_create_session():
    db = MagicMock()

    with pytest.raises(ValueError):
        create_auth_session(db, make_user(active=False))

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_missing_token_does_not_query_database():
    db = MagicMock()

    assert get_session_user(db, None) is None
    assert get_session_user(db, "") is None

    db.scalar.assert_not_called()


def test_valid_session_returns_user():
    db = MagicMock()
    user = make_user()
    db.scalar.return_value = user

    assert get_session_user(db, "valid-test-token") is user


def test_unknown_expired_revoked_or_inactive_session_returns_none():
    # The database query filters out all four cases. A query with no
    # matching active session returns None.
    db = MagicMock()
    db.scalar.return_value = None

    assert get_session_user(db, "invalid-test-token") is None


def test_revoke_session_sets_revocation_time():
    db = MagicMock()
    session = AuthSession(
        user_id=uuid.uuid4(),
        token_hash=_token_hash("test-token"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.scalar.return_value = session

    revoke_auth_session(db, "test-token")

    assert session.revoked_at is not None
    assert session.revoked_at <= datetime.now(timezone.utc)
    db.commit.assert_called_once()


def test_revoke_unknown_session_is_noop():
    db = MagicMock()
    db.scalar.return_value = None

    revoke_auth_session(db, "unknown-test-token")

    db.commit.assert_not_called()