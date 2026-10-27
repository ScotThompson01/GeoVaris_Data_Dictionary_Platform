"""Security tests for Data Quality rule activation API."""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app


def test_unauthenticated_user_cannot_activate_rule_version():
    project_id = uuid.uuid4()
    rule_id = uuid.uuid4()
    version_id = uuid.uuid4()

    with patch(
        "app.api.routes.data_quality_rules.activate_dq_rule_version"
    ) as activation_service:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/data-quality-rules/{rule_id}/versions/"
                f"{version_id}/activate",
                params={"project_id": str(project_id)},
            )

    assert response.status_code == 401
    activation_service.assert_not_called()


def test_authenticated_user_can_activate_rule_version():
    from app.api.dependencies.auth import (
        AuthenticatedSession,
        require_authenticated_session,
    )
    from app.db.session import get_db
    from app.models.user import User

    project_id = uuid.uuid4()
    rule_id = uuid.uuid4()
    version_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="dq_activation_api_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=False,
    )
    db = MagicMock()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="dq-activation-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch(
            "app.api.routes.data_quality_rules.activate_dq_rule_version",
            return_value=SimpleNamespace(
                id=rule_id,
                status="active",
                active_version_id=version_id,
            ),
        ) as activation_service:
            with TestClient(app) as client:
                response = client.post(
                    f"/api/v1/data-quality-rules/{rule_id}/versions/"
                    f"{version_id}/activate",
                    params={"project_id": str(project_id)},
                )

        assert response.status_code == 200
        assert response.json() == {
            "rule_id": str(rule_id),
            "version_id": str(version_id),
            "rule_status": "active",
            "active_version_id": str(version_id),
        }
        activation_service.assert_called_once_with(
            db,
            project_id=project_id,
            rule_id=rule_id,
            version_id=version_id,
            actor_user_id=user.id,
        )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)


def test_user_without_activation_permission_receives_403():
    from app.api.dependencies.auth import (
        AuthenticatedSession,
        require_authenticated_session,
    )
    from app.db.session import get_db
    from app.models.user import User

    project_id = uuid.uuid4()
    rule_id = uuid.uuid4()
    version_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="dq_activation_denied_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=False,
    )
    db = MagicMock()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="dq-activation-denied-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch(
            "app.api.routes.data_quality_rules.activate_dq_rule_version",
            side_effect=HTTPException(
                status_code=403,
                detail="Data Quality rule approval permission required.",
            ),
        ) as activation_service:
            with TestClient(app) as client:
                response = client.post(
                    f"/api/v1/data-quality-rules/{rule_id}/versions/"
                    f"{version_id}/activate",
                    params={"project_id": str(project_id)},
                )

        assert response.status_code == 403
        assert response.json() == {
            "detail": "Data Quality rule approval permission required."
        }
        activation_service.assert_called_once_with(
            db,
            project_id=project_id,
            rule_id=rule_id,
            version_id=version_id,
            actor_user_id=user.id,
        )
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)


def test_cross_project_activation_returns_404():
    from app.api.dependencies.auth import (
        AuthenticatedSession,
        require_authenticated_session,
    )
    from app.db.session import get_db
    from app.models.user import User

    project_id = uuid.uuid4()
    rule_id = uuid.uuid4()
    version_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        username="dq_cross_project_activation_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=False,
    )
    db = MagicMock()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="dq-cross-project-activation-test-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch(
            "app.api.routes.data_quality_rules.activate_dq_rule_version",
            side_effect=HTTPException(
                status_code=404,
                detail="Data Quality rule version not found.",
            ),
        ) as activation_service:
            with TestClient(app) as client:
                response = client.post(
                    f"/api/v1/data-quality-rules/{rule_id}/versions/"
                    f"{version_id}/activate",
                    params={"project_id": str(project_id)},
                )

        assert response.status_code == 404
        assert response.json() == {
            "detail": "Data Quality rule version not found."
        }
        activation_service.assert_called_once_with(
            db,
            project_id=project_id,
            rule_id=rule_id,
            version_id=version_id,
            actor_user_id=user.id,
        )
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)
