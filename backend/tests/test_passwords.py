import pytest

from app.core.passwords import hash_password, verify_password


def test_password_is_not_stored_as_plaintext():
    password = "Example-Test-Password-2026!"

    password_hash = hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$argon2id$")


def test_correct_password_verifies():
    password = "Example-Test-Password-2026!"
    password_hash = hash_password(password)

    assert verify_password(password, password_hash) is True


def test_incorrect_password_is_rejected():
    password_hash = hash_password("Example-Test-Password-2026!")

    assert verify_password("Wrong-Password", password_hash) is False


def test_invalid_hash_is_rejected():
    assert verify_password("Example-Test-Password-2026!", "invalid-hash") is False


def test_empty_password_cannot_be_hashed():
    with pytest.raises(ValueError):
        hash_password("")