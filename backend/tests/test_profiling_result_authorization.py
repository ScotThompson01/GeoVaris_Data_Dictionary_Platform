"""Profiling-result authorization tests using mocked database access."""

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
from app.models.data_source import DataSource
from app.models.profiling_result import ProfilingResult
from app.models.project_access import ProjectAccess
from app.models.scan import Scan
from app.models.user import User


def test_user_without_project_access_cannot_list_profiling_results():
    user = User(
        id=uuid.uuid4(),
        username="profiling_results_denied_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )

    db = MagicMock()
    db.scalars.return_value.all.return_value = []

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="profiling-results-denied-test-only-token",
        )

    def override_get_db():
        yield db

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/profiling-results")

        assert response.status_code == 200
        assert response.json() == []
        db.scalars.assert_called_once()
        actual_query = db.scalars.call_args.args[0]
        expected_query = (
            select(ProfilingResult)
            .join(Scan, Scan.id == ProfilingResult.scan_id)
            .join(DataSource, DataSource.id == Scan.data_source_id)
            .join(
                ProjectAccess,
                ProjectAccess.project_id == DataSource.project_id,
            )
            .where(ProjectAccess.user_id == user.id)
            .order_by(ProfilingResult.created_at.desc())
        )
        assert actual_query.compare(expected_query), (
            "Profiling-results listing must filter by the signed-in "
            "user's explicit project-access grants."
        )
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)


def test_user_without_project_access_cannot_get_profiling_result():
    profiling_result_id = uuid.uuid4()
    scan_id = uuid.uuid4()
    data_source_id = uuid.uuid4()
    project_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        username="profiling_result_detail_denied_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )

    db = MagicMock()
    db.get.side_effect = [
        ProfilingResult(id=profiling_result_id, scan_id=scan_id),
        Scan(id=scan_id, data_source_id=data_source_id),
        DataSource(id=data_source_id, project_id=project_id),
    ]
    db.scalar.return_value = None  # No explicit project grant.

    def override_authentication():
        return AuthenticatedSession(
            user=user,
            token="profiling-result-detail-denied-test-only-token",
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
                f"/api/v1/profiling-results/{profiling_result_id}"
            )

        assert response.status_code == 404
        assert response.json() == {
            "detail": "Profiling result not found."
        }
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
        app.dependency_overrides.pop(get_db, None)
