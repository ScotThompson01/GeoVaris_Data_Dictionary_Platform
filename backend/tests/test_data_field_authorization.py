"""Data-field authorization tests using mocked database access."""

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
from app.models.data_field import DataField
from app.models.data_source import DataSource
from app.models.project_access import ProjectAccess
from app.models.source_object import SourceObject
from app.models.user import User


def test_list_data_fields_filters_by_explicit_project_grants():
    user = User(
        id=uuid.uuid4(),
        username="data_field_list_authorization_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    now = datetime.now(timezone.utc)
    accessible_field = DataField(
        id=uuid.uuid4(),
        source_object_id=uuid.uuid4(),
        field_name="accessible_test_field",
        ordinal_position=1,
        native_data_type=None,
        normalized_data_type=None,
        max_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=None,
        is_primary_key=False,
        is_unique=False,
        default_value=None,
        source_comment=None,
        created_at=now,
        updated_at=now,
    )

    db = MagicMock()
    db.scalars.return_value.all.return_value = [accessible_field]

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="data-field-list-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/data-fields")

        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [
            str(accessible_field.id)
        ]

        db.scalars.assert_called_once()
        actual_query = db.scalars.call_args.args[0]
        expected_query = (
            select(DataField)
            .join(
                SourceObject,
                SourceObject.id == DataField.source_object_id,
            )
            .join(
                DataSource,
                DataSource.id == SourceObject.data_source_id,
            )
            .join(
                ProjectAccess,
                ProjectAccess.project_id == DataSource.project_id,
            )
            .where(ProjectAccess.user_id == user.id)
            .order_by(
                DataField.ordinal_position,
                DataField.field_name,
            )
        )
        assert actual_query.compare(expected_query), (
            "Data-field listing must filter by the signed-in "
            "user's explicit project-access grants."
        )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)

def test_user_without_project_access_cannot_create_data_field():
    source_object_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="data_field_create_denied_test_user",
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
            token="data-field-create-denied-test-only-token",
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
                "/api/v1/data-fields",
                json={
                    "source_object_id": str(source_object_id),
                    "field_name": "unauthorized_test_field",
                    "ordinal_position": 1,
                },
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "Source object not found."}
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

def test_user_without_project_access_cannot_get_data_field():
    data_field_id = uuid.uuid4()
    source_object_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="data_field_detail_denied_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    now = datetime.now(timezone.utc)
    data_field = DataField(
        id=data_field_id,
        source_object_id=source_object_id,
        field_name="restricted_test_field",
        ordinal_position=1,
        native_data_type=None,
        normalized_data_type=None,
        max_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=None,
        is_primary_key=False,
        is_unique=False,
        default_value=None,
        source_comment=None,
        created_at=now,
        updated_at=now,
    )
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
    db.get.side_effect = [data_field, source_object, data_source]
    db.scalar.return_value = None  # No explicit project grant.

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="data-field-detail-denied-test-only-token",
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
                f"/api/v1/data-fields/{data_field_id}"
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "Data field not found."}

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
