"""Field-governance authorization tests using mocked database access."""

import uuid
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


def test_user_without_project_access_cannot_get_field_governance():
    data_field_id = uuid.uuid4()
    source_object_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="field_governance_get_denied_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )

    data_field = DataField(
        id=data_field_id,
        source_object_id=source_object_id,
    )
    source_object = SourceObject(
        id=source_object_id,
        data_source_id=data_source_id,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )

    db = MagicMock()
    db.get.side_effect = [data_field, source_object, data_source]
    db.scalar.return_value = None  # No explicit project grant.

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="field-governance-get-denied-test-only-token",
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
                f"/api/v1/field-governance/{data_field_id}"
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


def test_user_without_project_access_cannot_save_field_governance():
    data_field_id = uuid.uuid4()
    source_object_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="field_governance_put_denied_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )

    data_field = DataField(
        id=data_field_id,
        source_object_id=source_object_id,
    )
    source_object = SourceObject(
        id=source_object_id,
        data_source_id=data_source_id,
    )
    data_source = DataSource(
        id=data_source_id,
        project_id=project_id,
    )

    db = MagicMock()
    db.get.side_effect = [data_field, source_object, data_source]
    db.scalar.return_value = None  # No explicit project grant.

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="field-governance-put-denied-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.put(
                f"/api/v1/field-governance/{data_field_id}",
                json={"business_name": "Unauthorized change"},
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "Data field not found."}
        db.add.assert_not_called()
        db.commit.assert_not_called()
        db.refresh.assert_not_called()

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
