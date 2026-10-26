"""API tests for project-level Administration settings."""

import uuid
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


def test_project_member_can_read_self_approval_setting():
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="settings_read_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=False,
    )
    project = Project(
        id=project_id,
        client_id=uuid.uuid4(),
        name="Synthetic settings test project",
        status="active",
        allow_steward_self_approval=False,
    )

    db = MagicMock()
    db.get.return_value = project
    db.scalar.return_value = uuid.uuid4()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="settings-read-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/projects/{project_id}/settings"
            )

        assert response.status_code == 200
        assert response.json() == {
            "project_id": str(project_id),
            "allow_steward_self_approval": False,
        }
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_user_without_project_access_cannot_read_settings():
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="settings_no_access_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )
    project = Project(
        id=project_id,
        client_id=uuid.uuid4(),
        name="Restricted synthetic project",
        status="active",
        allow_steward_self_approval=False,
    )

    db = MagicMock()
    db.get.return_value = project
    db.scalar.return_value = None

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="settings-no-access-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/projects/{project_id}/settings"
            )

        assert response.status_code == 404
        assert response.json() == {
            "detail": "Project not found."
        }
        db.get.assert_not_called()
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_project_administrator_can_enable_self_approval():
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="settings_admin_update_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )
    project = Project(
        id=project_id,
        client_id=uuid.uuid4(),
        name="Synthetic administration test project",
        status="active",
        allow_steward_self_approval=False,
    )

    db = MagicMock()
    db.get.return_value = project
    db.scalar.side_effect = [uuid.uuid4(), project]

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="settings-admin-update-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/api/v1/projects/{project_id}/settings",
                json={"allow_steward_self_approval": True},
            )

        assert response.status_code == 200
        assert response.json() == {
            "project_id": str(project_id),
            "allow_steward_self_approval": True,
        }
        assert project.allow_steward_self_approval is True
        db.commit.assert_called_once()

        audit_events = [
            call.args[0]
            for call in db.add.call_args_list
        ]
        assert len(audit_events) == 1

        from app.models.audit_event import AuditEvent

        event = audit_events[0]
        assert isinstance(event, AuditEvent)
        assert event.project_id == project_id
        assert event.actor_user_id == user.id
        assert event.event_type == (
            "project.steward_self_approval.changed"
        )
        assert event.old_value is False
        assert event.new_value is True
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_regular_project_member_cannot_change_self_approval():
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="settings_nonadmin_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=False,
    )
    project = Project(
        id=project_id,
        client_id=uuid.uuid4(),
        name="Synthetic restricted settings project",
        status="active",
        allow_steward_self_approval=False,
    )

    db = MagicMock()
    db.get.return_value = project
    db.scalar.return_value = uuid.uuid4()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="settings-nonadmin-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/api/v1/projects/{project_id}/settings",
                json={"allow_steward_self_approval": True},
            )

        assert response.status_code == 403
        assert response.json() == {
            "detail": "Project administration permission required."
        }
        assert project.allow_steward_self_approval is False
        db.get.assert_not_called()
        db.add.assert_not_called()
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_project_settings_patch_rejects_invalid_values():
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="settings_invalid_input_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )

    db = MagicMock()
    db.scalar.return_value = uuid.uuid4()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="settings-invalid-input-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    invalid_payloads = [
        {"allow_steward_self_approval": "yes"},
        {"allow_steward_self_approval": 1},
        {"allow_steward_self_approval": None},
        {},
        {
            "allow_steward_self_approval": True,
            "name": "Unauthorized project rename",
        },
    ]

    try:
        with TestClient(app) as client:
            for payload in invalid_payloads:
                response = client.patch(
                    f"/api/v1/projects/{project_id}/settings",
                    json=payload,
                )
                assert response.status_code == 422, (
                    f"Expected 422 for {payload}, "
                    f"received {response.status_code}"
                )

        db.get.assert_not_called()
        db.add.assert_not_called()
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_unchanged_self_approval_setting_does_not_create_audit_event():
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="settings_unchanged_test_admin",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )
    project = Project(
        id=project_id,
        client_id=uuid.uuid4(),
        name="Synthetic unchanged-settings project",
        status="active",
        allow_steward_self_approval=True,
    )

    db = MagicMock()
    db.get.return_value = project
    db.scalar.side_effect = [uuid.uuid4(), project]

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="settings-unchanged-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/api/v1/projects/{project_id}/settings",
                json={"allow_steward_self_approval": True},
            )

        assert response.status_code == 200
        assert response.json() == {
            "project_id": str(project_id),
            "allow_steward_self_approval": True,
        }
        assert project.allow_steward_self_approval is True

        db.add.assert_not_called()
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_administrator_without_project_access_cannot_change_settings():
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="settings_admin_no_project_access",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )
    project = Project(
        id=project_id,
        client_id=uuid.uuid4(),
        name="Synthetic inaccessible project",
        status="active",
        allow_steward_self_approval=False,
    )

    db = MagicMock()
    db.get.return_value = project
    db.scalar.return_value = None

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="settings-admin-no-access-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/api/v1/projects/{project_id}/settings",
                json={"allow_steward_self_approval": True},
            )

        assert response.status_code == 404
        assert response.json() == {
            "detail": "Project not found."
        }
        assert project.allow_steward_self_approval is False

        db.get.assert_not_called()
        db.add.assert_not_called()
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_inactive_administrator_cannot_change_settings():
    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="settings_inactive_admin_test_user",
        password_hash="test-only-placeholder",
        is_active=False,
        is_installation_admin=True,
    )
    project = Project(
        id=project_id,
        client_id=uuid.uuid4(),
        name="Synthetic inactive-admin test project",
        status="active",
        allow_steward_self_approval=False,
    )

    db = MagicMock()
    db.get.return_value = project
    db.scalar.return_value = uuid.uuid4()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="settings-inactive-admin-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/api/v1/projects/{project_id}/settings",
                json={"allow_steward_self_approval": True},
            )

        assert response.status_code == 403
        assert response.json() == {
            "detail": "Project administration permission required."
        }
        assert project.allow_steward_self_approval is False

        db.get.assert_not_called()
        db.add.assert_not_called()
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_settings_update_locks_project_row_before_modification():
    from sqlalchemy import select

    project_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="settings_row_lock_test_admin",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=True,
    )
    project = Project(
        id=project_id,
        client_id=uuid.uuid4(),
        name="Synthetic row-lock test project",
        status="active",
        allow_steward_self_approval=False,
    )

    db = MagicMock()
    db.scalar.side_effect = [
        uuid.uuid4(),  # Explicit project-access grant
        project,       # Project returned by the locking query
    ]

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="settings-row-lock-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/api/v1/projects/{project_id}/settings",
                json={"allow_steward_self_approval": True},
            )

        assert response.status_code == 200

        locking_query = db.scalar.call_args_list[1].args[0]
        expected_query = (
            select(Project)
            .where(Project.id == project_id)
            .with_for_update()
        )

        assert locking_query.compare(expected_query), (
            "Settings updates must lock the project row "
            "before reading and changing its current value."
        )
        db.commit.assert_called_once()
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)
