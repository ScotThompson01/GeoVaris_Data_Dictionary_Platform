import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.scan import Scan
import pytest

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.main import app
from app.models.user import User

@pytest.fixture(autouse=True)
def authenticated_discovery_requests():
    """Authenticate this module's requests without creating a real user."""
    test_user = User(
        id=uuid.uuid4(),
        username="discovery_test_user",
        password_hash="test-only-placeholder",
        is_active=True,
    )

    def override_authentication():
        return AuthenticatedSession(
            user=test_user,
            token="discovery-test-only-token",
        )

    app.dependency_overrides[require_authenticated_session] = (
        override_authentication
    )

    try:
        with patch(
            "app.api.routes.discovery.require_data_source_access"
        ):
            yield
    finally:
        app.dependency_overrides.pop(
            require_authenticated_session,
            None,
        )

client = TestClient(app)


@patch(
    "app.api.routes.discovery.discover_excel"
)
def test_excel_discovery_endpoint(
    mock_discover_excel,
):
    data_source_id = uuid.uuid4()
    scan_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_discover_excel.return_value = Scan(
        id=scan_id,
        data_source_id=data_source_id,
        scan_type="metadata",
        status="completed",
        started_at=now,
        completed_at=now,
        connector_version="0.2.0",
        created_at=now,
    )

    response = client.post(
        "/api/v1/discovery/excel",
        json={
            "data_source_id": str(data_source_id),
            "file_name": "customers.xlsx",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["id"] == str(scan_id)
    assert body["data_source_id"] == str(
        data_source_id
    )
    assert body["scan_type"] == "metadata"
    assert body["status"] == "completed"
    assert body["connector_version"] == "0.2.0"

    mock_discover_excel.assert_called_once()

    call_kwargs = mock_discover_excel.call_args.kwargs

    assert (
        call_kwargs["data_source_id"]
        == data_source_id
    )

    assert (
        call_kwargs["file_path"].name
        == "customers.xlsx"
    )


@patch(
    "app.api.routes.discovery.discover_excel"
)
def test_excel_discovery_rejects_path_traversal(
    mock_discover_excel,
):
    response = client.post(
        "/api/v1/discovery/excel",
        json={
            "data_source_id": str(uuid.uuid4()),
            "file_name": "../customers.xlsx",
        },
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "file_name must contain only a file name."
    )

    mock_discover_excel.assert_not_called()


@patch(
    "app.api.routes.discovery.discover_excel"
)
def test_excel_discovery_rejects_non_xlsx_file(
    mock_discover_excel,
):
    response = client.post(
        "/api/v1/discovery/excel",
        json={
            "data_source_id": str(uuid.uuid4()),
            "file_name": "customers.csv",
        },
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Excel discovery requires a .xlsx file."
    )

    mock_discover_excel.assert_not_called()


@patch(
    "app.api.routes.discovery.discover_excel"
)
def test_excel_discovery_returns_not_found(
    mock_discover_excel,
):
    mock_discover_excel.side_effect = FileNotFoundError(
        "Sensitive internal path should not be returned."
    )

    response = client.post(
        "/api/v1/discovery/excel",
        json={
            "data_source_id": str(uuid.uuid4()),
            "file_name": "missing.xlsx",
        },
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Excel file not found."
    )

    assert (
        "Sensitive internal path"
        not in response.text
    )


@patch(
    "app.api.routes.discovery.discover_excel"
)
def test_excel_discovery_sanitizes_unexpected_error(
    mock_discover_excel,
):
    sensitive_detail = (
        "Unexpected workbook failure at "
        "/data/samples/private/customer.xlsx"
    )

    mock_discover_excel.side_effect = RuntimeError(
        sensitive_detail
    )

    response = client.post(
        "/api/v1/discovery/excel",
        json={
            "data_source_id": str(uuid.uuid4()),
            "file_name": "customers.xlsx",
        },
    )

    assert response.status_code == 500

    assert (
        response.json()["detail"]
        == "Excel discovery failed."
    )

    assert sensitive_detail not in response.text