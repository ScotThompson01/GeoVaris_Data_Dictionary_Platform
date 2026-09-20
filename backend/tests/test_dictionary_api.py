import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app


client = TestClient(app)


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
        app.dependency_overrides.clear()