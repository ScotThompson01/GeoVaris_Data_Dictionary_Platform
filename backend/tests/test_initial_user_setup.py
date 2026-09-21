from unittest.mock import MagicMock, patch

from app.cli.create_initial_user import create_initial_user


def test_existing_user_prevents_initial_setup():
    db = MagicMock()
    db.scalar.return_value = object()

    with (
        patch("app.cli.create_initial_user.SessionLocal") as session_factory,
        patch("builtins.input", return_value="initialuser"),
        patch(
            "app.cli.create_initial_user.getpass.getpass",
            side_effect=["Example-Test-Password-2026!", "Example-Test-Password-2026!"],
        ),
        patch("app.cli.create_initial_user.hash_password") as hash_password,
    ):
        session_factory.return_value.__enter__.return_value = db

        result = create_initial_user()

    assert result == 1
    db.add.assert_not_called()
    db.commit.assert_not_called()
    hash_password.assert_not_called()


def test_initial_setup_creates_one_hashed_user():
    db = MagicMock()
    db.scalar.return_value = None

    with (
        patch("app.cli.create_initial_user.SessionLocal") as session_factory,
        patch("builtins.input", return_value="initialuser"),
        patch(
            "app.cli.create_initial_user.getpass.getpass",
            side_effect=["Example-Test-Password-2026!", "Example-Test-Password-2026!"],
        ),
        patch(
            "app.cli.create_initial_user.hash_password",
            return_value="$argon2id$test-hash",
        ),
    ):
        session_factory.return_value.__enter__.return_value = db

        result = create_initial_user()

    assert result == 0
    db.add.assert_called_once()
    db.commit.assert_called_once()

    user = db.add.call_args.args[0]
    assert user.username == "initialuser"
    assert user.password_hash == "$argon2id$test-hash"
    assert user.is_active is True