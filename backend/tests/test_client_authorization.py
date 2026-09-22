"""Client authorization tests using an in-memory user and mocked database."""

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
from app.models.client import Client
from app.models.user import User


def test_user_without_client_access_cannot_get_client():
    client_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="client_authorization_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    now = datetime.now(timezone.utc)
    client_record = Client(
        id=client_id,
        name="Restricted test client",
        created_at=now,
        updated_at=now,
    )

    db = MagicMock()
    db.get.return_value = client_record
    db.scalar.return_value = None

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="client-authorization-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.get(f"/api/v1/clients/{client_id}")

        assert response.status_code == 404
        assert response.json() == {"detail": "Client not found."}
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_user_with_client_access_can_get_client():
    client_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="client_access_granted_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    now = datetime.now(timezone.utc)
    client_record = Client(
        id=client_id,
        name="Accessible test client",
        created_at=now,
        updated_at=now,
    )

    db = MagicMock()
    db.get.return_value = client_record
    db.scalar.return_value = uuid.uuid4()  # Represents an existing grant ID.

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="client-access-granted-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.get(f"/api/v1/clients/{client_id}")

        assert response.status_code == 200
        assert response.json()["id"] == str(client_id)
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_list_clients_returns_only_explicitly_granted_clients():
    from sqlalchemy import select

    from app.models.client_access import ClientAccess

    user = User(
        id=uuid.uuid4(),
        username="client_list_authorization_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    now = datetime.now(timezone.utc)
    accessible_client = Client(
        id=uuid.uuid4(),
        name="Accessible list test client",
        description=None,
        created_at=now,
        updated_at=now,
    )

    db = MagicMock()
    db.scalars.return_value.all.return_value = [accessible_client]

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="client-list-authorization-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/clients")

        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [
            str(accessible_client.id)
        ]

        db.scalars.assert_called_once()
        actual_query = db.scalars.call_args.args[0]
        expected_query = (
            select(Client)
            .join(ClientAccess, ClientAccess.client_id == Client.id)
            .where(ClientAccess.user_id == user.id)
            .order_by(Client.name)
        )
        assert actual_query.compare(expected_query), (
            "Client list query must filter by the signed-in user's "
            "explicit client-access grants."
        )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_authenticated_user_cannot_create_client_without_provisioning_permission():
    user = User(
        id=uuid.uuid4(),
        username="client_creation_authorization_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    db = MagicMock()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="client-creation-authorization-test-only-token",
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
                "/api/v1/clients",
                json={"name": "Unauthorized test client"},
            )

        assert response.status_code == 403
        db.add.assert_not_called()
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)
