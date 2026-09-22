"""Project authorization tests using an in-memory user and mocked database."""

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
from app.models.project import Project
from app.models.user import User


def test_user_without_project_access_cannot_get_project():
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="project_authorization_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    now = datetime.now(timezone.utc)
    project = Project(
        id=project_id,
        client_id=uuid.uuid4(),
        name="Restricted test project",
        status="active",
        created_at=now,
        updated_at=now,
    )

    db = MagicMock()
    db.get.return_value = project
    db.scalar.return_value = None

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="project-authorization-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/projects/{project_id}")

        assert response.status_code == 404
        assert response.json() == {"detail": "Project not found."}
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)



def test_user_with_project_access_can_get_project():
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="project_access_granted_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    now = datetime.now(timezone.utc)
    project = Project(
        id=project_id,
        client_id=uuid.uuid4(),
        name="Accessible test project",
        status="active",
        created_at=now,
        updated_at=now,
    )

    db = MagicMock()
    db.get.return_value = project
    db.scalar.return_value = uuid.uuid4()  # Represents an existing grant ID.

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="project-access-granted-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/projects/{project_id}")

        assert response.status_code == 200
        assert response.json()["id"] == str(project_id)
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_list_projects_returns_only_explicitly_granted_projects():
    from sqlalchemy import select

    from app.models.project_access import ProjectAccess

    user = User(
        id=uuid.uuid4(),
        username="project_list_authorization_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    now = datetime.now(timezone.utc)
    accessible_project = Project(
        id=uuid.uuid4(),
        client_id=uuid.uuid4(),
        name="Accessible list test project",
        description=None,
        status="active",
        created_at=now,
        updated_at=now,
    )

    db = MagicMock()
    db.scalars.return_value.all.return_value = [accessible_project]

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="project-list-authorization-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/projects")

        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [
            str(accessible_project.id)
        ]

        db.scalars.assert_called_once()
        actual_query = db.scalars.call_args.args[0]
        expected_query = (
            select(Project)
            .join(ProjectAccess, ProjectAccess.project_id == Project.id)
            .where(ProjectAccess.user_id == user.id)
            .order_by(Project.name)
        )
        assert actual_query.compare(expected_query), (
            "Project list query must filter by the signed-in user's "
            "explicit project-access grants."
        )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_authenticated_user_cannot_create_project_without_provisioning_permission():
    user = User(
        id=uuid.uuid4(),
        username="project_creation_authorization_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )
    db = MagicMock()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="project-creation-authorization-test-only-token",
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
                "/api/v1/projects",
                json={
                    "client_id": str(uuid.uuid4()),
                    "name": "Unauthorized test project",
                },
            )

        assert response.status_code == 403
        db.add.assert_not_called()
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)
