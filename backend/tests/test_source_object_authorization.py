"""Source-object authorization tests using mocked database access."""

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
from app.models.source_object import SourceObject
from app.models.user import User


def test_list_source_objects_filters_by_explicit_project_grants():
    user = User(
        id=uuid.uuid4(),
        username="source_object_list_authorization_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    now = datetime.now(timezone.utc)
    accessible_object = SourceObject(
        id=uuid.uuid4(),
        data_source_id=uuid.uuid4(),
        object_type="table",
        object_name="Accessible test table",
        schema_name=None,
        native_name=None,
        description=None,
        row_count=None,
        created_at=now,
        updated_at=now,
    )

    db = MagicMock()
    db.scalars.return_value.all.return_value = [accessible_object]

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="source-object-list-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/source-objects")

        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [
            str(accessible_object.id)
        ]

        db.scalars.assert_called_once()
        actual_query = db.scalars.call_args.args[0]
        expected_query = (
            select(SourceObject)
            .join(
                DataSource,
                DataSource.id == SourceObject.data_source_id,
            )
            .join(
                ProjectAccess,
                ProjectAccess.project_id == DataSource.project_id,
            )
            .where(ProjectAccess.user_id == user.id)
            .order_by(SourceObject.object_name)
        )
        assert actual_query.compare(expected_query), (
            "Source-object listing must filter by the signed-in "
            "user's explicit project-access grants."
        )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_user_without_project_access_cannot_get_source_object():
    source_object_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="source_object_detail_denied_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    now = datetime.now(timezone.utc)
    source_object = SourceObject(
        id=source_object_id,
        data_source_id=data_source_id,
        object_type="table",
        object_name="Restricted test table",
        schema_name=None,
        native_name=None,
        description=None,
        row_count=None,
        created_at=now,
        updated_at=now,
    )
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
    db.get.side_effect = [source_object, data_source]
    db.scalar.return_value = None  # No explicit project grant.

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="source-object-detail-denied-test-only-token",
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
                f"/api/v1/source-objects/{source_object_id}"
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "Source object not found."}

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


def test_user_without_project_access_cannot_create_source_object():
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="source_object_create_denied_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    now = datetime.now(timezone.utc)
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
        name="Restricted creation test data source",
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
            token="source-object-create-denied-test-only-token",
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
                "/api/v1/source-objects",
                json={
                    "data_source_id": str(data_source_id),
                    "object_type": "table",
                    "object_name": "Unauthorized test table",
                },
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "Data source not found."}
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
