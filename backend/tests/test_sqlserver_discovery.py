import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.connectors.base import (
    DiscoveredField,
    DiscoveredObject,
)
from app.connectors.database.base import DatabaseConnectionConfig
from app.models.data_source import DataSource
from app.models.scan import Scan
from app.services.sqlserver_discovery import discover_sqlserver


@patch(
    "app.services.sqlserver_discovery.persist_discovered_object"
)
@patch(
    "app.services.sqlserver_discovery.SQLServerConnector"
)
def test_discover_sqlserver_persists_objects_and_completes_scan(
    mock_connector_class,
    mock_persist,
):
    data_source_id = uuid.uuid4()
    scan_id = uuid.uuid4()

    data_source = DataSource(
        id=data_source_id,
        project_id=uuid.uuid4(),
        name="Test SQL Server",
        source_type="sqlserver",
        connection_mode="database",
        is_active=True,
    )

    scan = Scan(
        id=scan_id,
        data_source_id=data_source_id,
        scan_type="metadata",
        status="running",
    )

    discovered = DiscoveredObject(
        object_type="table",
        object_name="customers",
        native_name="dbo.customers",
        schema_name="dbo",
        fields=[
            DiscoveredField(
                field_name="customer_id",
                ordinal_position=1,
                native_data_type="int",
                normalized_data_type="integer",
                is_nullable=False,
                is_primary_key=True,
                is_unique=True,
            )
        ],
    )

    connector = mock_connector_class.return_value
    connector.connector_version = "0.2.0"
    connector.discover_objects.return_value = [
        discovered
    ]

    db = MagicMock()

    db.get.side_effect = [
        data_source,
        scan,
    ]

    db.refresh.side_effect = None

    config = DatabaseConnectionConfig(
        host="sqlserver.internal",
        port=1433,
        database="customer_database",
        username="readonly_user",
    )

    result = discover_sqlserver(
        db=db,
        data_source_id=data_source_id,
        connection_config=config,
        password="runtime-only-password",
    )

    connector.validate_connection.assert_called_once_with(
        config=config,
        password="runtime-only-password",
    )

    connector.discover_objects.assert_called_once_with(
        config=config,
        password="runtime-only-password",
    )

    mock_persist.assert_called_once_with(
        db=db,
        data_source=data_source,
        discovered=discovered,
    )

    assert result.status == "completed"
    assert result.completed_at is not None
    assert result.error_message is None

    assert db.commit.call_count == 2


@patch(
    "app.services.sqlserver_discovery.SQLServerConnector"
)
def test_discover_sqlserver_marks_scan_failed_on_connection_error(
    mock_connector_class,
):
    data_source_id = uuid.uuid4()
    scan_id = uuid.uuid4()

    data_source = DataSource(
        id=data_source_id,
        project_id=uuid.uuid4(),
        name="Test SQL Server",
        source_type="sqlserver",
        connection_mode="database",
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
    connector.validate_connection.side_effect = ConnectionError(
        "Unable to connect to SQL Server."
    )

    db = MagicMock()

    db.get.side_effect = [
        data_source,
        scan,
    ]

    db.refresh.side_effect = None

    config = DatabaseConnectionConfig(
        host="sqlserver.internal",
        port=1433,
        database="customer_database",
        username="readonly_user",
    )

    with pytest.raises(
        ConnectionError,
        match="Unable to connect to SQL Server",
    ):
        discover_sqlserver(
            db=db,
            data_source_id=data_source_id,
            connection_config=config,
            password="runtime-only-password",
        )

    assert scan.status == "failed"
    assert scan.completed_at is not None
    assert scan.error_message == "Unable to connect to SQL Server."

    db.rollback.assert_called_once()
    assert db.commit.call_count == 2

def test_discover_sqlserver_rejects_missing_data_source():
    data_source_id = uuid.uuid4()

    db = MagicMock()
    db.get.return_value = None

    config = DatabaseConnectionConfig(
        host="sqlserver.internal",
        port=1433,
        database="customer_database",
        username="readonly_user",
    )

    with pytest.raises(
        ValueError,
        match="Data source not found",
    ):
        discover_sqlserver(
            db=db,
            data_source_id=data_source_id,
            connection_config=config,
            password="runtime-only-password",
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_discover_sqlserver_rejects_wrong_source_type():
    data_source = DataSource(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        name="Wrong Source",
        source_type="postgresql",
        connection_mode="database",
        is_active=True,
    )

    db = MagicMock()
    db.get.return_value = data_source

    config = DatabaseConnectionConfig(
        host="sqlserver.internal",
        port=1433,
        database="customer_database",
        username="readonly_user",
    )

    with pytest.raises(ValueError):
        discover_sqlserver(
            db=db,
            data_source_id=data_source.id,
            connection_config=config,
            password="runtime-only-password",
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_discover_sqlserver_rejects_inactive_data_source():
    data_source = DataSource(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        name="Inactive SQL Server",
        source_type="sqlserver",
        connection_mode="database",
        is_active=False,
    )

    db = MagicMock()
    db.get.return_value = data_source

    config = DatabaseConnectionConfig(
        host="sqlserver.internal",
        port=1433,
        database="customer_database",
        username="readonly_user",
    )

    with pytest.raises(ValueError):
        discover_sqlserver(
            db=db,
            data_source_id=data_source.id,
            connection_config=config,
            password="runtime-only-password",
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()