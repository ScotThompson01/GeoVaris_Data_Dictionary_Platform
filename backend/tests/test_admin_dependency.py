"""Tests for installation administrator authorization."""

import uuid

import pytest
from fastapi import HTTPException

from app.api.dependencies.admin import require_installation_admin
from app.api.dependencies.auth import AuthenticatedSession
from app.models.user import User


def make_session(
    *,
    is_installation_admin: bool,
    is_active: bool = True,
) -> AuthenticatedSession:
    user = User(
        id=uuid.uuid4(),
        username="testuser",
        password_hash="test-only-placeholder",
        is_active=is_active,
        is_installation_admin=is_installation_admin,
    )
    return AuthenticatedSession(user=user, token="test-token")


def test_installation_admin_is_allowed():
    session = make_session(is_installation_admin=True)

    result = require_installation_admin(session)

    assert result is session.user


def test_regular_user_is_rejected():
    session = make_session(is_installation_admin=False)

    with pytest.raises(HTTPException) as error:
        require_installation_admin(session)

    assert error.value.status_code == 403
    assert error.value.detail == "Administrator access required."


def test_inactive_installation_admin_is_rejected():
    session = make_session(
        is_installation_admin=True,
        is_active=False,
    )

    with pytest.raises(HTTPException) as error:
        require_installation_admin(session)

    assert error.value.status_code == 403
    assert error.value.detail == "Administrator access required."
