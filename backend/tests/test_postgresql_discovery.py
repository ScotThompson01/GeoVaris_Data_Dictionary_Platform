import uuid
from unittest.mock import MagicMock, patch

from app.connectors.base import (
    DiscoveredField,
    DiscoveredObject,
)
from app.connectors.database.base import DatabaseConnectionConfig
from app.models.data_source import DataSource
from app.models.scan import Scan
from app.services.postgresql_discovery import discover_postgresql


@patch(
    "app.services.postgresql_discovery.persist_discovered_object"
)
@patch(
    "app.services.postgresql_discovery.PostgreSQLConnector"
)
def test_discover_postgresql_persists_objects_and_completes_scan(
    mock_connector_class,
    mock_persist,
):
    data_source_id = uuid.uuid4()
    scan_id = uuid.uuid4()

    data_source = DataSource(
        id=data_source_id,
        project_id=uuid.uuid4(),
        name="Test PostgreSQL",
        source_type="postgresql",
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
        native_name="public.customers",
        schema_name="public",
        fields=[
            DiscoveredField(
                field_name="customer_id",
                ordinal_position=1,
                native_data_type="uuid",
                normalized_data_type="uuid",
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
        host="postgres.internal",
        port=5432,
        database="customer_database",
        username="readonly_user",
    )

    result = discover_postgresql(
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