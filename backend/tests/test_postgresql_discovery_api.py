import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.scan import Scan
import pytest

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.main import app
from app.models.user import User

client = TestClient(app)

@pytest.fixture(autouse=True)
def authenticated_discovery_requests():
    """Authenticate this module's requests without creating a real user."""
    test_user = User(
        id=uuid.uuid4(),
        username="discovery_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )

    def override_authentication():
        return AuthenticatedSession(
            user=test_user,
            token="discovery-test-only-token",
        )

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )

    try:
        yield
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session,
            None,
        )

@patch(
    "app.api.routes.discovery.discover_postgresql"
)
def test_postgresql_discovery_endpoint(
    mock_discover_postgresql,
):
    data_source_id = uuid.uuid4()
    scan_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_discover_postgresql.return_value = Scan(
        id=scan_id,
        data_source_id=data_source_id,
        scan_type="metadata",
        status="completed",
        started_at=now,
        completed_at=now,
        connector_version="0.2.0",
        created_at=now,
    )

    response = client.post(
        "/api/v1/discovery/postgresql",
        json={
            "data_source_id": str(data_source_id),
            "host": "database.example.internal",
            "port": 5432,
            "database": "customer_data",
            "username": "readonly_user",
            "password": "runtime-only-password",
            "ssl_mode": None,
            "connect_timeout_seconds": 10,
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["id"] == str(scan_id)
    assert body["data_source_id"] == str(
        data_source_id
    )
    assert body["scan_type"] == "metadata"
    assert body["status"] == "completed"
    assert body["connector_version"] == "0.2.0"

    # Runtime connection secrets must never be exposed
    # in the API response.
    assert (
        "runtime-only-password"
        not in response.text
    )

    mock_discover_postgresql.assert_called_once()

    call_kwargs = (
        mock_discover_postgresql.call_args.kwargs
    )

    assert (
        call_kwargs["data_source_id"]
        == data_source_id
    )

    connection_config = (
        call_kwargs["connection_config"]
    )

    assert (
        connection_config.host
        == "database.example.internal"
    )
    assert connection_config.port == 5432
    assert (
        connection_config.database
        == "customer_data"
    )
    assert (
        connection_config.username
        == "readonly_user"
    )
    assert (
        connection_config.connect_timeout_seconds
        == 10
    )

    assert (
        call_kwargs["password"]
        == "runtime-only-password"
    )


@patch(
    "app.api.routes.discovery.discover_postgresql"
)
def test_postgresql_discovery_sanitizes_connection_error(
    mock_discover_postgresql,
):
    data_source_id = uuid.uuid4()
    secret = "super-secret-database-password"

    mock_discover_postgresql.side_effect = ConnectionError(
        f"Connection failed using password {secret}"
    )

    response = client.post(
        "/api/v1/discovery/postgresql",
        json={
            "data_source_id": str(data_source_id),
            "host": "database.example.internal",
            "port": 5432,
            "database": "customer_data",
            "username": "readonly_user",
            "password": secret,
            "ssl_mode": None,
            "connect_timeout_seconds": 10,
        },
    )

    assert response.status_code == 400
    assert secret not in response.text

    assert (
        response.json()["detail"]
        == (
            "Unable to connect to or discover metadata "
            "from the PostgreSQL source."
        )
    )


@patch(
    "app.api.routes.discovery.discover_postgresql"
)
def test_postgresql_discovery_rejects_invalid_port(
    mock_discover_postgresql,
):
    response = client.post(
        "/api/v1/discovery/postgresql",
        json={
            "data_source_id": str(uuid.uuid4()),
            "host": "database.example.internal",
            "port": 70000,
            "database": "customer_data",
            "username": "readonly_user",
            "password": "runtime-only-password",
            "ssl_mode": None,
            "connect_timeout_seconds": 10,
        },
    )

    assert response.status_code == 422

    assert (
        "runtime-only-password"
        not in response.text
    )

    mock_discover_postgresql.assert_not_called()