"""HTTP-level authorization tests for User Management."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.db.session import get_db
from app.main import app
from app.models.user import User


def make_user(*, is_installation_admin: bool) -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        username="testuser",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=is_installation_admin,
        created_at=now,
        updated_at=now,
    )


def request_user_list(user: User, db: MagicMock):
    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            return test_client.get("/api/v1/user-management")
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)


def test_regular_user_cannot_list_users():
    user = make_user(is_installation_admin=False)
    db = MagicMock()

    response = request_user_list(user, db)

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Administrator access required."
    }
    db.scalars.assert_not_called()


def test_installation_admin_can_list_users_without_secrets():
    user = make_user(is_installation_admin=True)
    db = MagicMock()
    db.scalars.return_value.all.return_value = [user]

    response = request_user_list(user, db)

    assert response.status_code == 200
    assert response.json() == [
        {
            "user_id": str(user.id),
            "username": user.username,
            "is_active": True,
            "is_installation_admin": True,
            "created_at": user.created_at.isoformat().replace(
                "+00:00", "Z"
            ),
            "updated_at": user.updated_at.isoformat().replace(
                "+00:00", "Z"
            ),
        }
    ]
    assert "password_hash" not in response.text
    assert "test-only-token" not in response.text

def test_regular_user_cannot_create_users():
    user = make_user(is_installation_admin=False)
    db = MagicMock()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/v1/user-management",
                json={
                    "username": "newuser",
                    "password": "test-only-password-123",
                },
            )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Administrator access required."
    }
    db.add.assert_not_called()
    db.commit.assert_not_called()

def test_installation_admin_can_create_standard_user():
    from unittest.mock import patch

    admin = make_user(is_installation_admin=True)
    db = MagicMock()
    created_at = datetime.now(timezone.utc)

    def override_authentication():
        return AuthenticatedSession(
            user=admin,
            token="test-only-token",
        )

    def override_get_db():
        yield db

    def populate_created_user(user):
        user.id = uuid.uuid4()
        user.created_at = created_at
        user.updated_at = created_at

    db.refresh.side_effect = populate_created_user

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch(
            "app.api.routes.user_management.hash_password",
            return_value="test-only-hash",
        ) as mock_hash:
            with TestClient(app) as test_client:
                response = test_client.post(
                    "/api/v1/user-management",
                    json={
                        "username": "newuser",
                        "password": "test-only-password-123",
                    },
                )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 201
    mock_hash.assert_called_once_with("test-only-password-123")
    db.add.assert_called_once()
    db.commit.assert_called_once()

    created_user = db.add.call_args.args[0]
    assert created_user.username == "newuser"
    assert created_user.password_hash == "test-only-hash"
    assert created_user.is_active is True
    assert created_user.is_installation_admin is False

    body = response.json()
    assert body["username"] == "newuser"
    assert body["is_active"] is True
    assert body["is_installation_admin"] is False
    assert "password" not in response.text
    assert "test-only-hash" not in response.text

def test_create_user_rejects_duplicate_username():
    from sqlalchemy.exc import IntegrityError
    from unittest.mock import patch

    admin = make_user(is_installation_admin=True)
    db = MagicMock()
    db.commit.side_effect = IntegrityError(
        "INSERT INTO users",
        {},
        Exception("duplicate username"),
    )

    def override_authentication():
        return AuthenticatedSession(
            user=admin,
            token="test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch(
            "app.api.routes.user_management.hash_password",
            return_value="test-only-hash",
        ):
            with TestClient(app) as test_client:
                response = test_client.post(
                    "/api/v1/user-management",
                    json={
                        "username": "existinguser",
                        "password": "test-only-password-123",
                    },
                )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Username is already in use."
    }
    db.rollback.assert_called_once()
    db.refresh.assert_not_called()
    assert "test-only-password-123" not in response.text

def test_create_user_rejects_invalid_input():
    import pytest

    admin = make_user(is_installation_admin=True)
    db = MagicMock()

    def override_authentication():
        return AuthenticatedSession(
            user=admin,
            token="test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    invalid_requests = [
        {"username": "ab", "password": "test-only-password-123"},
        {"username": "invalid user", "password": "test-only-password-123"},
        {"username": "newuser", "password": "short"},
        {"username": "newuser", "password": "x" * 1025},
    ]

    try:
        with TestClient(app) as test_client:
            for payload in invalid_requests:
                response = test_client.post(
                    "/api/v1/user-management",
                    json=payload,
                )
                assert response.status_code == 422
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    db.add.assert_not_called()
    db.commit.assert_not_called()

def test_invalid_password_is_not_exposed_in_validation_response():
    admin = make_user(is_installation_admin=True)
    db = MagicMock()
    invalid_password = "Q7!xP"

    def override_authentication():
        return AuthenticatedSession(
            user=admin,
            token="test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/v1/user-management",
                json={
                    "username": "newuser",
                    "password": invalid_password,
                },
            )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 422
    assert invalid_password not in response.text
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_installation_admin_can_promote_another_user():
    admin = make_user(is_installation_admin=True)
    target = make_user(is_installation_admin=False)
    target.username = "otheruser"
    db = MagicMock()
    db.get.return_value = target

    def override_authentication():
        return AuthenticatedSession(
            user=admin,
            token="test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.patch(
                f"/api/v1/user-management/{target.id}/role",
                json={"is_installation_admin": True},
            )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert target.is_installation_admin is True
    db.commit.assert_called_once()
    assert response.json()["is_installation_admin"] is True


def test_installation_admin_cannot_demote_self():
    admin = make_user(is_installation_admin=True)
    db = MagicMock()
    db.get.return_value = admin

    def override_authentication():
        return AuthenticatedSession(
            user=admin,
            token="test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.patch(
                f"/api/v1/user-management/{admin.id}/role",
                json={"is_installation_admin": False},
            )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 409
    assert admin.is_installation_admin is True
    db.commit.assert_not_called()


def test_installation_admin_can_demote_another_admin():
    admin = make_user(is_installation_admin=True)
    target = make_user(is_installation_admin=True)
    target.username = "otheradmin"
    db = MagicMock()
    db.get.return_value = target

    def override_authentication():
        return AuthenticatedSession(
            user=admin,
            token="test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.patch(
                f"/api/v1/user-management/{target.id}/role",
                json={"is_installation_admin": False},
            )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert target.is_installation_admin is False
    db.commit.assert_called_once()
    assert response.json()["is_installation_admin"] is False


def test_standard_user_cannot_change_another_users_role():
    standard_user = make_user(is_installation_admin=False)
    target = make_user(is_installation_admin=False)
    db = MagicMock()

    def override_authentication():
        return AuthenticatedSession(
            user=standard_user,
            token="test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.patch(
                f"/api/v1/user-management/{target.id}/role",
                json={"is_installation_admin": True},
            )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 403
    db.get.assert_not_called()
    db.commit.assert_not_called()
