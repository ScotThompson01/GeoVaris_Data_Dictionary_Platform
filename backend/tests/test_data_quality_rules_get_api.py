"""Security and empty-result tests for Data Quality rule retrieval."""

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.db.session import get_db
from app.main import app
from app.models.data_field import DataField
from app.models.data_source import DataSource
from app.models.source_object import SourceObject


def test_get_rules_requires_authentication():
    app.dependency_overrides.clear()
    field_id = uuid.uuid4()

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/data-quality-rules",
            params={"data_field_id": str(field_id)},
        )

    assert response.status_code == 401


def test_get_rules_rejects_unauthorized_project():
    field_id = uuid.uuid4()
    object_id = uuid.uuid4()
    source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()

    db = MagicMock()
    db.get.side_effect = [
        SimpleNamespace(source_object_id=object_id),
        SimpleNamespace(data_source_id=source_id),
        SimpleNamespace(project_id=project_id),
    ]
    db.scalar.return_value = None

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_authenticated_session] = (
        lambda: AuthenticatedSession(
            user=SimpleNamespace(id=user_id),
            token="synthetic-test-token",
        )
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/data-quality-rules",
                params={"data_field_id": str(field_id)},
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Data field not found."
        db.scalars.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )


def test_get_rules_returns_empty_list_for_authorized_field():
    field_id = uuid.uuid4()
    object_id = uuid.uuid4()
    source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()

    db = MagicMock()
    db.get.side_effect = [
        SimpleNamespace(source_object_id=object_id),
        SimpleNamespace(data_source_id=source_id),
        SimpleNamespace(project_id=project_id),
    ]
    db.scalar.return_value = uuid.uuid4()
    db.scalars.return_value.all.return_value = []

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_authenticated_session] = (
        lambda: AuthenticatedSession(
            user=SimpleNamespace(id=user_id),
            token="synthetic-test-token",
        )
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/data-quality-rules",
                params={"data_field_id": str(field_id)},
            )

        assert response.status_code == 200
        assert response.json() == []
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )


def test_get_rules_returns_version_history():
    field_id = uuid.uuid4()
    object_id = uuid.uuid4()
    source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()
    rule_id = uuid.uuid4()
    version_id = uuid.uuid4()

    db = MagicMock()
    db.get.side_effect = [
        SimpleNamespace(source_object_id=object_id),
        SimpleNamespace(data_source_id=source_id),
        SimpleNamespace(project_id=project_id),
    ]
    db.scalar.return_value = uuid.uuid4()

    rule = SimpleNamespace(
        id=rule_id,
        data_field_id=field_id,
        rule_name="Latitude Range",
        status="draft",
        active_version_id=None,
    )
    version = SimpleNamespace(
        id=version_id,
        rule_id=rule_id,
        version_number=1,
        rule_type="range",
        quality_dimension="validity",
        min_value=Decimal("-90"),
        max_value=Decimal("90"),
        null_allowed=False,
        status="draft",
    )

    db.scalars.side_effect = [
        SimpleNamespace(all=lambda: [rule]),
        SimpleNamespace(all=lambda: [version]),
    ]

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_authenticated_session] = (
        lambda: AuthenticatedSession(
            user=SimpleNamespace(id=user_id),
            token="synthetic-test-token",
        )
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/data-quality-rules",
                params={"data_field_id": str(field_id)},
            )

        assert response.status_code == 200, response.text

        results = response.json()
        assert len(results) == 1
        assert results[0]["rule_id"] == str(rule_id)
        assert results[0]["data_field_id"] == str(field_id)
        assert results[0]["rule_name"] == "Latitude Range"
        assert results[0]["status"] == "draft"
        assert results[0]["active_version_id"] is None

        assert len(results[0]["versions"]) == 1
        stored_version = results[0]["versions"][0]
        assert stored_version["version_id"] == str(version_id)
        assert stored_version["version_number"] == 1
        assert Decimal(str(stored_version["min_value"])) == Decimal("-90")
        assert Decimal(str(stored_version["max_value"])) == Decimal("90")
        assert stored_version["null_allowed"] is False
        assert stored_version["status"] == "draft"

        assert db.scalars.call_count == 2
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(
            require_authenticated_session, None
        )
