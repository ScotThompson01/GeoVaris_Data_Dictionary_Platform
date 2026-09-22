"""Data-source authorization tests using mocked database access."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.db.session import get_db
from app.main import app
from app.models.data_source import DataSource
from app.models.project_access import ProjectAccess
from app.models.user import User


def test_list_data_sources_filters_by_explicit_project_grants():
    user = User(
        id=uuid.uuid4(),
        username="data_source_list_authorization_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    now = datetime.now(timezone.utc)
    accessible_source = DataSource(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        name="Accessible test data source",
        source_type="csv",
        description=None,
        connection_mode="file",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    db = MagicMock()
    db.scalars.return_value.all.return_value = [accessible_source]

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="data-source-list-authorization-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/data-sources")

        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [
            str(accessible_source.id)
        ]

        db.scalars.assert_called_once()
        actual_query = db.scalars.call_args.args[0]
        expected_query = (
            select(DataSource)
            .join(
                ProjectAccess,
                ProjectAccess.project_id == DataSource.project_id,
            )
            .where(ProjectAccess.user_id == user.id)
            .order_by(DataSource.name)
        )
        assert actual_query.compare(expected_query), (
            "Data-source listing must filter by the signed-in user's "
            "explicit project-access grants."
        )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)

def test_list_data_sources_project_filter_preserves_access_grants():
    user = User(
        id=uuid.uuid4(),
        username="data_source_project_filter_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    requested_project_id = uuid.uuid4()
    db = MagicMock()
    db.scalars.return_value.all.return_value = []

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="data-source-project-filter-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.get(
                "/api/v1/data-sources",
                params={"project_id": str(requested_project_id)},
            )

        assert response.status_code == 200
        assert response.json() == []

        db.scalars.assert_called_once()
        actual_query = db.scalars.call_args.args[0]
        expected_query = (
            select(DataSource)
            .join(
                ProjectAccess,
                ProjectAccess.project_id == DataSource.project_id,
            )
            .where(ProjectAccess.user_id == user.id)
            .where(DataSource.project_id == requested_project_id)
            .order_by(DataSource.name)
        )
        assert actual_query.compare(expected_query), (
            "Filtering by project must not remove the user's "
            "explicit project-access restriction."
        )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)

def test_user_without_project_access_cannot_get_data_source():
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="data_source_detail_denied_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    now = datetime.now(timezone.utc)
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
        name="Restricted test data source",
        source_type="csv",
        description=None,
        connection_mode="file",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    db = MagicMock()
    db.get.return_value = data_source
    db.scalar.return_value = None  # No explicit project grant.

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="data-source-detail-denied-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.get(
                f"/api/v1/data-sources/{data_source_id}"
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "Data source not found."}
        db.scalar.assert_called_once()
        grant_query = db.scalar.call_args.args[0]
        expected_grant_query = select(ProjectAccess.id).where(
            ProjectAccess.user_id == user.id,
            ProjectAccess.project_id == project_id,
        )
        assert grant_query.compare(expected_grant_query)
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_user_without_project_access_cannot_create_data_source():
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="data_source_create_denied_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )

    db = MagicMock()
    db.get.return_value = MagicMock(id=project_id)
    db.scalar.return_value = None  # No explicit project grant.

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="data-source-create-denied-test-only-token",
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
                "/api/v1/data-sources",
                json={
                    "project_id": str(project_id),
                    "name": "Unauthorized test data source",
                    "source_type": "csv",
                    "connection_mode": "file",
                },
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "Project not found."}
        db.add.assert_not_called()
        db.commit.assert_not_called()

        db.scalar.assert_called_once()
        grant_query = db.scalar.call_args.args[0]
        expected_grant_query = select(ProjectAccess.id).where(
            ProjectAccess.user_id == user.id,
            ProjectAccess.project_id == project_id,
        )
        assert grant_query.compare(expected_grant_query)
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)
