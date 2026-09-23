"""HTTP tests for dictionary request validation and project filtering."""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.db.session import get_db
from app.main import app
from app.models.user import User


client = TestClient(app)


@pytest.fixture(autouse=True)
def authenticated_dictionary_requests():
    """Authenticate requests in this test module without creating a real user."""
    test_user = User(
        id=uuid.uuid4(),
        username="dictionary_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )

    def override_authentication():
        return AuthenticatedSession(
            user=test_user,
            token="dictionary-test-only-token",
        )

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )

    try:
        yield
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session,
            None,
        )


def test_dictionary_requires_project_id():
    response = client.get("/api/v1/dictionary")

    assert response.status_code == 422


def test_dictionary_rejects_invalid_project_id():
    response = client.get(
        "/api/v1/dictionary",
        params={"project_id": "not-a-uuid"},
    )

    assert response.status_code == 422


def test_dictionary_filters_by_project():
    project_id = uuid.uuid4()
    db = MagicMock()

    # Return no rows; this test checks the generated SQL filter.
    db.execute.return_value.mappings.return_value.all.return_value = []

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get(
            "/api/v1/dictionary",
            params={"project_id": str(project_id)},
        )

        assert response.status_code == 200
        assert response.json() == []

        statement = db.execute.call_args.args[0]
        sql = str(statement.compile())

        assert "data_sources.project_id" in sql
        assert project_id in statement.compile().params.values()
    finally:
        app.dependency_overrides.pop(get_db, None)

def test_dictionary_filters_non_cde_fields():
    project_id = uuid.uuid4()
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = []

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get(
            "/api/v1/dictionary",
            params={
                "project_id": str(project_id),
                "is_cde": "false",
            },
        )

        assert response.status_code == 200
        assert response.json() == []

        statement = db.execute.call_args.args[0]
        compiled = statement.compile()
        sql = str(compiled)

        assert "coalesce" in sql.lower()
        assert "field_governance_metadata.is_cde" in sql
        assert False in compiled.params.values()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_dictionary_combines_source_department_and_owner_filters():
    project_id = uuid.uuid4()
    source_id = uuid.uuid4()
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = []

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get(
            "/api/v1/dictionary",
            params={
                "project_id": str(project_id),
                "data_source_id": str(source_id),
                "department": "Operations",
                "data_owner": "Test Owner",
            },
        )

        assert response.status_code == 200
        assert response.json() == []

        statement = db.execute.call_args.args[0]
        compiled = statement.compile()
        sql = str(compiled)
        values = compiled.params.values()

        assert "data_sources.project_id" in sql
        assert "data_sources.id" in sql
        assert "field_governance_metadata.department" in sql
        assert "field_governance_metadata.data_owner" in sql
        assert project_id in values
        assert source_id in values
        assert "Operations" in values
        assert "Test Owner" in values
    finally:
        app.dependency_overrides.pop(get_db, None)