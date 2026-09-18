import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.connectors.base import (
    DiscoveredField,
    DiscoveredObject,
)
from app.models.data_source import DataSource
from app.models.scan import Scan
from app.services.excel_discovery import discover_excel


@patch(
    "app.services.excel_discovery.persist_discovered_object"
)
@patch(
    "app.services.excel_discovery.ExcelConnector"
)
def test_discover_excel_persists_worksheets_and_completes_scan(
    mock_connector_class,
    mock_persist,
):
    data_source_id = uuid.uuid4()
    scan_id = uuid.uuid4()

    data_source = DataSource(
        id=data_source_id,
        project_id=uuid.uuid4(),
        name="Test Excel",
        source_type="excel",
        connection_mode="file",
        is_active=True,
    )

    scan = Scan(
        id=scan_id,
        data_source_id=data_source_id,
        scan_type="metadata",
        status="running",
    )

    customers = DiscoveredObject(
        object_type="worksheet",
        object_name="Customers",
        native_name="customers.xlsx:Customers",
        row_count=2,
        fields=[
            DiscoveredField(
                field_name="customer_id",
                ordinal_position=1,
                native_data_type="integer",
                normalized_data_type="integer",
                is_nullable=False,
            )
        ],
    )

    orders = DiscoveredObject(
        object_type="worksheet",
        object_name="Orders",
        native_name="customers.xlsx:Orders",
        row_count=1,
        fields=[
            DiscoveredField(
                field_name="order_id",
                ordinal_position=1,
                native_data_type="integer",
                normalized_data_type="integer",
                is_nullable=False,
            )
        ],
    )

    connector = mock_connector_class.return_value
    connector.connector_version = "0.2.0"
    connector.discover_workbook.return_value = [
        customers,
        orders,
    ]

    db = MagicMock()

    db.get.side_effect = [
        data_source,
        scan,
    ]

    db.refresh.side_effect = None

    file_path = Path(
        "/data/samples/customers.xlsx"
    )

    result = discover_excel(
        db=db,
        data_source_id=data_source_id,
        file_path=file_path,
    )

    connector.discover_workbook.assert_called_once_with(
        file_path
    )

    assert mock_persist.call_count == 2

    mock_persist.assert_any_call(
        db=db,
        data_source=data_source,
        discovered=customers,
    )

    mock_persist.assert_any_call(
        db=db,
        data_source=data_source,
        discovered=orders,
    )

    assert result.status == "completed"
    assert result.completed_at is not None
    assert result.error_message is None

    assert db.commit.call_count == 2


def test_discover_excel_rejects_missing_data_source():
    data_source_id = uuid.uuid4()

    db = MagicMock()
    db.get.return_value = None

    with pytest.raises(
        ValueError,
        match="Data source not found",
    ):
        discover_excel(
            db=db,
            data_source_id=data_source_id,
            file_path=Path(
                "/data/samples/customers.xlsx"
            ),
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_discover_excel_rejects_wrong_source_type():
    data_source = DataSource(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        name="Wrong Source",
        source_type="csv",
        connection_mode="file",
        is_active=True,
    )

    db = MagicMock()
    db.get.return_value = data_source

    with pytest.raises(
        ValueError,
        match="Excel discovery requires an Excel data source",
    ):
        discover_excel(
            db=db,
            data_source_id=data_source.id,
            file_path=Path(
                "/data/samples/customers.xlsx"
            ),
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_discover_excel_rejects_inactive_data_source():
    data_source = DataSource(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        name="Inactive Excel",
        source_type="excel",
        connection_mode="file",
        is_active=False,
    )

    db = MagicMock()
    db.get.return_value = data_source

    with pytest.raises(
        ValueError,
        match="active data source",
    ):
        discover_excel(
            db=db,
            data_source_id=data_source.id,
            file_path=Path(
                "/data/samples/customers.xlsx"
            ),
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()


@patch(
    "app.services.excel_discovery.ExcelConnector"
)
def test_discover_excel_marks_scan_failed_on_discovery_error(
    mock_connector_class,
):
    data_source_id = uuid.uuid4()
    scan_id = uuid.uuid4()

    data_source = DataSource(
        id=data_source_id,
        project_id=uuid.uuid4(),
        name="Test Excel",
        source_type="excel",
        connection_mode="file",
        is_active=True,
    )

    scan = Scan(
        id=scan_id,
        data_source_id=data_source_id,
        scan_type="metadata",
        status="running",
    )

    connector = mock_connector_class.return_value
    connector.connector_version = "0.2.0"
    connector.discover_workbook.side_effect = ValueError(
        "Workbook discovery failed."
    )

    db = MagicMock()

    db.get.side_effect = [
        data_source,
        scan,
    ]

    db.refresh.side_effect = None

    with pytest.raises(
        ValueError,
        match="Workbook discovery failed",
    ):
        discover_excel(
            db=db,
            data_source_id=data_source_id,
            file_path=Path(
                "/data/samples/customers.xlsx"
            ),
        )

    assert scan.status == "failed"
    assert scan.completed_at is not None
    assert (
        scan.error_message
        == "Workbook discovery failed."
    )

    db.rollback.assert_called_once()
    assert db.commit.call_count == 2