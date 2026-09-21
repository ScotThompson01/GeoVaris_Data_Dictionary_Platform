"""Tests for the protected-route authentication dependency."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Request

from app.api.dependencies.auth import require_authenticated_session
from app.models.user import User


def make_request(authorization: str | None = None) -> Request:
    headers = []

    if authorization is not None:
        headers.append(
            (b"authorization", authorization.encode("ascii"))
        )

    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/clients",
            "headers": headers,
        }
    )


def make_user() -> User:
    return User(
        id=uuid.uuid4(),
        username="testuser",
        password_hash="test-only-placeholder",
        is_active=True,
    )


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "",
        "Basic credentials",
        "Bearer",
        "Bearer ",
        "Bearer token with spaces",
        "Bearer  token",
    ],
)
def test_missing_or_malformed_authorization_is_rejected(authorization):
    db = MagicMock()

    with pytest.raises(HTTPException) as error:
        require_authenticated_session(
            make_request(authorization),
            db,
        )

    assert error.value.status_code == 401
    assert error.value.detail == "Authentication required."
    db.scalar.assert_not_called()


def test_unknown_session_is_rejected():
    db = MagicMock()

    with patch(
        "app.api.dependencies.auth.get_session_user",
        return_value=None,
    ) as lookup:
        with pytest.raises(HTTPException) as error:
            require_authenticated_session(
                make_request("Bearer invalid-token"),
                db,
            )

    assert error.value.status_code == 401
    lookup.assert_called_once_with(db, "invalid-token")


def test_valid_session_returns_user_and_token():
    db = MagicMock()
    user = make_user()

    with patch(
        "app.api.dependencies.auth.get_session_user",
        return_value=user,
    ):
        result = require_authenticated_session(
            make_request("Bearer valid-token"),
            db,
        )

    assert result.user is user
    assert result.token == "valid-token"