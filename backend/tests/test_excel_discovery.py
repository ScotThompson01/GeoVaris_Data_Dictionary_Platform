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
from app.models.source_object import SourceObject
from app.services.excel_discovery import discover_excel


def _make_data_source(
    *,
    source_type: str = "excel",
    is_active: bool = True,
) -> DataSource:
    return DataSource(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        name="Test Excel",
        source_type=source_type,
        connection_mode="file",
        is_active=is_active,
    )


def _make_scan(
    data_source_id: uuid.UUID,
) -> Scan:
    return Scan(
        id=uuid.uuid4(),
        data_source_id=data_source_id,
        scan_type="metadata",
        status="running",
    )


def _configure_scan_refresh(
    db: MagicMock,
    scan: Scan,
) -> None:
    """
    Simulate SQLAlchemy assigning the persisted scan ID when the
    newly created Scan is refreshed.

    MagicMock does not reproduce SQLAlchemy's insert/default behavior,
    so the service-created Scan would otherwise keep id=None.
    """

    def refresh_side_effect(instance):
        if isinstance(instance, Scan) and instance.id is None:
            instance.id = scan.id

    db.refresh.side_effect = refresh_side_effect


@patch(
    "app.services.excel_discovery.profile_excel_worksheet"
)
@patch(
    "app.services.excel_discovery.persist_discovered_object"
)
@patch(
    "app.services.excel_discovery.ExcelConnector"
)
def test_discover_excel_persists_profiles_and_completes_scan(
    mock_connector_class,
    mock_persist,
    mock_profile,
):
    data_source = _make_data_source()
    scan = _make_scan(data_source.id)

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

    customer_object = SourceObject(
        id=uuid.uuid4(),
        data_source_id=data_source.id,
        object_type="worksheet",
        object_name="Customers",
    )

    order_object = SourceObject(
        id=uuid.uuid4(),
        data_source_id=data_source.id,
        object_type="worksheet",
        object_name="Orders",
    )

    connector = mock_connector_class.return_value
    connector.connector_version = "0.2.0"
    connector.discover_workbook.return_value = [
        customers,
        orders,
    ]

    mock_persist.side_effect = [
        customer_object,
        order_object,
    ]

    db = MagicMock()

    _configure_scan_refresh(
        db=db,
        scan=scan,
    )

    db.get.side_effect = [
        data_source,
        scan,
    ]

    file_path = Path(
        "/data/samples/customers.xlsx"
    )

    result = discover_excel(
        db=db,
        data_source_id=data_source.id,
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

    assert mock_profile.call_count == 2

    mock_profile.assert_any_call(
        db=db,
        scan_id=scan.id,
        source_object_id=customer_object.id,
        file_path=file_path,
    )

    mock_profile.assert_any_call(
        db=db,
        scan_id=scan.id,
        source_object_id=order_object.id,
        file_path=file_path,
    )

    assert result.status == "completed"
    assert result.completed_at is not None
    assert result.error_message is None

    # Scan creation and final completion are committed here.
    # Worksheet persistence/profiling commits are mocked.
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
    data_source = _make_data_source(
        source_type="csv",
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
    data_source = _make_data_source(
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
    data_source = _make_data_source()
    scan = _make_scan(data_source.id)

    connector = mock_connector_class.return_value
    connector.connector_version = "0.2.0"
    connector.discover_workbook.side_effect = ValueError(
        "Workbook discovery failed."
    )

    db = MagicMock()

    _configure_scan_refresh(
        db=db,
        scan=scan,
    )

    db.get.side_effect = [
        data_source,
        scan,
    ]

    with pytest.raises(
        ValueError,
        match="Workbook discovery failed",
    ):
        discover_excel(
            db=db,
            data_source_id=data_source.id,
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


@patch(
    "app.services.excel_discovery.profile_excel_worksheet"
)
@patch(
    "app.services.excel_discovery.persist_discovered_object"
)
@patch(
    "app.services.excel_discovery.ExcelConnector"
)
def test_discover_excel_marks_scan_failed_on_profiling_error(
    mock_connector_class,
    mock_persist,
    mock_profile,
):
    data_source = _make_data_source()
    scan = _make_scan(data_source.id)

    customers = DiscoveredObject(
        object_type="worksheet",
        object_name="Customers",
        native_name="customers.xlsx:Customers",
        row_count=1,
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

    customer_object = SourceObject(
        id=uuid.uuid4(),
        data_source_id=data_source.id,
        object_type="worksheet",
        object_name="Customers",
    )

    connector = mock_connector_class.return_value
    connector.connector_version = "0.2.0"
    connector.discover_workbook.return_value = [
        customers
    ]

    mock_persist.return_value = customer_object

    mock_profile.side_effect = ValueError(
        "Worksheet profiling failed."
    )

    db = MagicMock()

    _configure_scan_refresh(
        db=db,
        scan=scan,
    )

    db.get.side_effect = [
        data_source,
        scan,
    ]

    file_path = Path(
        "/data/samples/customers.xlsx"
    )

    with pytest.raises(
        ValueError,
        match="Worksheet profiling failed",
    ):
        discover_excel(
            db=db,
            data_source_id=data_source.id,
            file_path=file_path,
        )

    mock_profile.assert_called_once_with(
        db=db,
        scan_id=scan.id,
        source_object_id=customer_object.id,
        file_path=file_path,
    )

    assert scan.status == "failed"
    assert scan.completed_at is not None
    assert (
        scan.error_message
        == "Worksheet profiling failed."
    )

    db.rollback.assert_called_once()
    assert db.commit.call_count == 2