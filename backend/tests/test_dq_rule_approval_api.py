"""Security tests for Data Quality rule approval API."""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def test_unauthenticated_user_cannot_approve_rule_version():
    """Unauthenticated requests must not reach the approval service."""
    project_id = uuid.uuid4()
    rule_id = uuid.uuid4()
    version_id = uuid.uuid4()

    with patch(
        "app.api.routes.data_quality_rules.approve_dq_rule_version"
    ) as approval_service:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/data-quality-rules/{rule_id}/versions/"
                f"{version_id}/approve",
                params={"project_id": str(project_id)},
            )

    assert response.status_code == 401
    approval_service.assert_not_called()


def test_authenticated_user_can_approve_rule_version():
    """The endpoint must pass authenticated identity to the approval service."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock

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
        username="dq_approval_api_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=False,
    )

    db = MagicMock()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="dq-approval-api-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch(
            "app.api.routes.data_quality_rules.approve_dq_rule_version",
            return_value=SimpleNamespace(id=version_id, status="approved"),
        ) as approval_service:
            with TestClient(app) as client:
                response = client.post(
                    f"/api/v1/data-quality-rules/{rule_id}/versions/"
                    f"{version_id}/approve",
                    params={"project_id": str(project_id)},
                )

        assert response.status_code == 200
        assert response.json() == {
            "rule_id": str(rule_id),
            "version_id": str(version_id),
            "version_status": "approved",
        }
        approval_service.assert_called_once_with(
            db,
            project_id=project_id,
            rule_id=rule_id,
            version_id=version_id,
            actor_user_id=user.id,
        )
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_user_without_approval_permission_receives_403():
    """The endpoint must preserve an approval-permission denial."""
    from unittest.mock import MagicMock

    from fastapi import HTTPException

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
        username="dq_approval_denied_api_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=False,
    )

    db = MagicMock()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="dq-approval-denied-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch(
            "app.api.routes.data_quality_rules.approve_dq_rule_version",
            side_effect=HTTPException(
                status_code=403,
                detail="Approval permission required.",
            ),
        ) as approval_service:
            with TestClient(app) as client:
                response = client.post(
                    f"/api/v1/data-quality-rules/{rule_id}/versions/"
                    f"{version_id}/approve",
                    params={"project_id": str(project_id)},
                )

        assert response.status_code == 403
        assert response.json() == {
            "detail": "Approval permission required."
        }
        approval_service.assert_called_once_with(
            db,
            project_id=project_id,
            rule_id=rule_id,
            version_id=version_id,
            actor_user_id=user.id,
        )
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)


def test_cross_project_approval_returns_404():
    """The endpoint must preserve a cross-project access denial."""
    from unittest.mock import MagicMock

    from fastapi import HTTPException

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
        username="dq_cross_project_api_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
        is_installation_admin=False,
    )

    db = MagicMock()

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="dq-cross-project-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch(
            "app.api.routes.data_quality_rules.approve_dq_rule_version",
            side_effect=HTTPException(
                status_code=404,
                detail="Data Quality rule not found.",
            ),
        ) as approval_service:
            with TestClient(app) as client:
                response = client.post(
                    f"/api/v1/data-quality-rules/{rule_id}/versions/"
                    f"{version_id}/approve",
                    params={"project_id": str(project_id)},
                )

        assert response.status_code == 404
        assert response.json() == {
            "detail": "Data Quality rule not found."
        }
        approval_service.assert_called_once_with(
            db,
            project_id=project_id,
            rule_id=rule_id,
            version_id=version_id,
            actor_user_id=user.id,
        )
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(require_authenticated_session, None)
        app.dependency_overrides.pop(get_db, None)
