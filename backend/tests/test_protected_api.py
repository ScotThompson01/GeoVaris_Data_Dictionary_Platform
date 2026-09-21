"""HTTP-level checks that data routes reject unauthenticated requests."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/clients"),
        ("POST", "/api/v1/clients"),
        ("GET", "/api/v1/projects"),
        ("GET", "/api/v1/data-sources"),
        ("GET", "/api/v1/scans"),
        ("GET", "/api/v1/source-objects"),
        ("GET", "/api/v1/data-fields"),
        ("GET", "/api/v1/dictionary"),
        ("GET", "/api/v1/profiling-results"),
        ("GET", "/api/v1/field-governance/00000000-0000-0000-0000-000000000000"),
        ("POST", "/api/v1/discovery/csv"),
    ],
)
def test_data_routes_require_authentication(method: str, path: str):
    response = client.request(method, path)

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}

def test_logout_requires_authentication():
    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication required."
    }
