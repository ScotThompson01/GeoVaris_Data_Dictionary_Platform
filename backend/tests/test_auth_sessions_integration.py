"""PostgreSQL integration tests for authentication sessions.

Runs only against the designated disposable auth_test_db database.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models.auth_session import AuthSession
from app.models.user import User
from app.services.auth_sessions import (
    _token_hash,
    create_auth_session,
    get_session_user,
    revoke_auth_session,
)


@pytest.fixture
def test_engine():
    database_url = os.environ.get("AUTH_TEST_DATABASE_URL")

    if not database_url:
        pytest.skip("AUTH_TEST_DATABASE_URL is not configured.")

    parsed_url = make_url(database_url)

    if (
        parsed_url.drivername != "postgresql+psycopg"
        or parsed_url.host != "auth_test_db"
        or parsed_url.database != "geovaris_auth_test"
        or parsed_url.username != "geovaris_auth_test"
    ):
        pytest.fail("Refusing to run against a non-isolated database.")

    engine = create_engine(database_url, pool_pre_ping=True)

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def test_user(test_engine):
    """Create a test user and delete it after the test."""
    user_id = uuid.uuid4()

    with Session(test_engine) as db:
        db.add(
            User(
                id=user_id,
                username=f"session_test_{user_id.hex}",
                password_hash="test-only-placeholder",
                is_active=True,
            )
        )
        db.commit()

    try:
        yield user_id
    finally:
        # auth_sessions.user_id has ON DELETE CASCADE.
        with Session(test_engine) as db:
            user = db.get(User, user_id)
            if user is not None:
                db.delete(user)
                db.commit()


def test_valid_session_authenticates(test_engine, test_user):
    with Session(test_engine) as db:
        user = db.get(User, test_user)
        token = create_auth_session(db, user)

        authenticated_user = get_session_user(db, token)

        assert authenticated_user is not None
        assert authenticated_user.id == test_user

        stored_session = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == _token_hash(token)
            )
        )

        assert stored_session is not None
        assert stored_session.token_hash != token


def test_expired_session_is_rejected(test_engine, test_user):
    with Session(test_engine) as db:
        user = db.get(User, test_user)
        token = create_auth_session(db, user)

        stored_session = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == _token_hash(token)
            )
        )

        stored_session.expires_at = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        db.commit()

    with Session(test_engine) as db:
        assert get_session_user(db, token) is None


def test_revoked_session_is_rejected(test_engine, test_user):
    with Session(test_engine) as db:
        user = db.get(User, test_user)
        token = create_auth_session(db, user)

        revoke_auth_session(db, token)

    with Session(test_engine) as db:
        assert get_session_user(db, token) is None


def test_inactive_user_session_is_rejected(test_engine, test_user):
    with Session(test_engine) as db:
        user = db.get(User, test_user)
        token = create_auth_session(db, user)

        user.is_active = False
        db.commit()

    with Session(test_engine) as db:
        assert get_session_user(db, token) is None


def test_unknown_token_is_rejected(test_engine, test_user):
    with Session(test_engine) as db:
        assert get_session_user(db, "not-a-real-session-token") is None