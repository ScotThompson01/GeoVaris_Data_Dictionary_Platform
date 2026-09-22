"""Discovery authorization tests using mocked database access."""

import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.db.session import get_db
from app.main import app
from app.models.data_source import DataSource
from app.models.user import User


def test_user_without_project_access_cannot_run_csv_discovery():
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="csv_discovery_denied_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )

    db = MagicMock()
    db.get.return_value = data_source
    db.scalar.return_value = None  # No explicit project grant.

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="csv-discovery-denied-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch(
            "app.api.routes.discovery.discover_csv"
        ) as mocked_discover:
            with TestClient(app) as test_client:
                response = test_client.post(
                    "/api/v1/discovery/csv",
                    json={
                        "data_source_id": str(data_source_id),
                        "file_name": "sample.csv",
                    },
                )

            assert response.status_code == 404
            assert response.json() == {
                "detail": "Data source not found."
            }
            mocked_discover.assert_not_called()
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)


def test_user_without_project_access_cannot_run_excel_discovery():
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="excel_discovery_denied_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )

    db = MagicMock()
    db.get.return_value = data_source
    db.scalar.return_value = None  # No explicit project grant.

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="excel-discovery-denied-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch(
            "app.api.routes.discovery.discover_excel"
        ) as mocked_discover:
            with TestClient(app) as test_client:
                response = test_client.post(
                    "/api/v1/discovery/excel",
                    json={
                        "data_source_id": str(data_source_id),
                        "file_name": "sample.xlsx",
                    },
                )

            assert response.status_code == 404
            assert response.json() == {
                "detail": "Data source not found."
            }
            mocked_discover.assert_not_called()
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)


def test_user_without_project_access_cannot_run_postgresql_discovery():
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="postgresql_discovery_denied_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )

    db = MagicMock()
    db.get.return_value = data_source
    db.scalar.return_value = None  # No explicit project grant.

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="postgresql-discovery-denied-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch(
            "app.api.routes.discovery.discover_postgresql"
        ) as mocked_discover:
            with TestClient(app) as test_client:
                response = test_client.post(
                    "/api/v1/discovery/postgresql",
                    json={
                        "data_source_id": str(data_source_id),
                        "host": "localhost",
                        "database": "test_db",
                        "username": "test_user",
                    },
                )

            assert response.status_code == 404
            assert response.json() == {
                "detail": "Data source not found."
            }
            mocked_discover.assert_not_called()
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)


def test_user_without_project_access_cannot_run_sqlserver_discovery():
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="sqlserver_discovery_denied_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )

    db = MagicMock()
    db.get.return_value = data_source
    db.scalar.return_value = None  # No explicit project grant.

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="sqlserver-discovery-denied-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch(
            "app.api.routes.discovery.discover_sqlserver"
        ) as mocked_discover:
            with TestClient(app) as test_client:
                response = test_client.post(
                    "/api/v1/discovery/sqlserver",
                    json={
                        "data_source_id": str(data_source_id),
                        "host": "localhost",
                        "database": "test_db",
                        "username": "test_user",
                    },
                )

            assert response.status_code == 404
            assert response.json() == {
                "detail": "Data source not found."
            }
            mocked_discover.assert_not_called()
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)
