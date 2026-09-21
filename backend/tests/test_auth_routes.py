"""Focused tests for the backend authentication routes."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.dependencies.auth import AuthenticatedSession
from app.api.routes.auth import logout, sign_in
from app.models.user import User
from app.schemas.auth import SignInRequest


def make_user(*, active: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        username="testuser",
        password_hash="test-only-hash",
        is_active=active,
    )


def test_sign_in_returns_session_token_for_valid_credentials():
    db = MagicMock()
    user = make_user()
    db.scalar.return_value = user

    with (
        patch(
            "app.api.routes.auth.verify_password",
            return_value=True,
        ) as verify,
        patch(
            "app.api.routes.auth.create_auth_session",
            return_value="test-session-token",
        ) as create_session,
    ):
        result = sign_in(
            SignInRequest(
                username="testuser",
                password="test-password",
            ),
            db,
        )

    assert result.session_token == "test-session-token"
    assert result.user_id == user.id
    assert result.username == user.username

    verify.assert_called_once_with(
        "test-password",
        user.password_hash,
    )
    create_session.assert_called_once_with(db, user)


@pytest.mark.parametrize(
    ("user", "password_matches"),
    [
        (None, False),
        (make_user(active=False), True),
        (make_user(active=True), False),
    ],
)
def test_sign_in_rejects_invalid_credentials(
    user: User | None,
    password_matches: bool,
):
    db = MagicMock()
    db.scalar.return_value = user

    with (
        patch(
            "app.api.routes.auth.verify_password",
            return_value=password_matches,
        ),
        patch(
            "app.api.routes.auth.create_auth_session",
        ) as create_session,
    ):
        with pytest.raises(HTTPException) as error:
            sign_in(
                SignInRequest(
                    username="testuser",
                    password="incorrect-password",
                ),
                db,
            )

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid username or password."
    create_session.assert_not_called()


def test_logout_revokes_authenticated_session():
    db = MagicMock()
    user = make_user()

    authenticated = AuthenticatedSession(
        user=user,
        token="authenticated-test-token",
    )

    with patch(
        "app.api.routes.auth.revoke_auth_session"
    ) as revoke:
        logout(authenticated, db)

    revoke.assert_called_once_with(
        db,
        "authenticated-test-token",
    )