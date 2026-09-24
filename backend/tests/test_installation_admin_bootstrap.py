"""Tests for first installation administrator bootstrap safeguards."""

import uuid
from unittest.mock import MagicMock, patch

from app.cli.bootstrap_installation_admin import (
    bootstrap_installation_admin,
)
from app.models.user import User


def make_user() -> User:
    return User(
        id=uuid.uuid4(),
        username="existinguser",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=False,
    )


def test_existing_administrator_prevents_bootstrap():
    db = MagicMock()
    db.scalar.return_value = uuid.uuid4()

    with (
        patch(
            "app.cli.bootstrap_installation_admin.SessionLocal"
        ) as session_factory,
        patch("builtins.input", return_value="existinguser"),
        patch(
            "app.cli.bootstrap_installation_admin.getpass.getpass",
            return_value="test-only-password",
        ),
        patch(
            "app.cli.bootstrap_installation_admin.verify_password"
        ) as verify_password,
    ):
        session_factory.return_value.__enter__.return_value = db
        result = bootstrap_installation_admin()

    assert result == 1
    db.commit.assert_not_called()
    verify_password.assert_not_called()


def test_incorrect_password_does_not_grant_administrator_role():
    user = make_user()
    db = MagicMock()
    db.scalar.side_effect = [None, user]

    with (
        patch(
            "app.cli.bootstrap_installation_admin.SessionLocal"
        ) as session_factory,
        patch("builtins.input", return_value=user.username),
        patch(
            "app.cli.bootstrap_installation_admin.getpass.getpass",
            return_value="incorrect-test-password",
        ),
        patch(
            "app.cli.bootstrap_installation_admin.verify_password",
            return_value=False,
        ),
    ):
        session_factory.return_value.__enter__.return_value = db
        result = bootstrap_installation_admin()

    assert result == 1
    assert user.is_installation_admin is False
    db.commit.assert_not_called()


def test_verified_user_becomes_first_installation_administrator():
    user = make_user()
    db = MagicMock()
    db.scalar.side_effect = [None, user]

    with (
        patch(
            "app.cli.bootstrap_installation_admin.SessionLocal"
        ) as session_factory,
        patch("builtins.input", return_value=user.username),
        patch(
            "app.cli.bootstrap_installation_admin.getpass.getpass",
            return_value="correct-test-password",
        ),
        patch(
            "app.cli.bootstrap_installation_admin.verify_password",
            return_value=True,
        ) as verify_password,
    ):
        session_factory.return_value.__enter__.return_value = db
        result = bootstrap_installation_admin()

    assert result == 0
    assert user.is_installation_admin is True
    db.commit.assert_called_once()
    verify_password.assert_called_once_with(
        "correct-test-password",
        user.password_hash,
    )
