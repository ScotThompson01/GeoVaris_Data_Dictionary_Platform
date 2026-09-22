"""Dictionary authorization tests using mocked database access."""

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
from app.models.project_access import ProjectAccess
from app.models.user import User


def test_user_without_project_access_cannot_list_dictionary_fields():
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="dictionary_denied_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )

    db = MagicMock()
    db.scalar.return_value = None  # No explicit project grant.

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="dictionary-denied-test-only-token",
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
                "/api/v1/dictionary",
                params={"project_id": str(project_id)},
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "Project not found."}
        db.execute.assert_not_called()

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
