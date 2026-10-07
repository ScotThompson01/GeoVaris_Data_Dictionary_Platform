import uuid
from unittest.mock import MagicMock

from app.connectors.base import DiscoveredObject
from app.models.data_source import DataSource
from app.services.discovery_persistence import persist_discovered_object


def test_persist_discovered_object_uses_full_namespace_identity():
    data_source_id = uuid.uuid4()

    data_source = DataSource(
        id=data_source_id,
        project_id=uuid.uuid4(),
        name="Test Databricks",
        source_type="databricks",
        connection_mode="database",
        is_active=True,
    )

    discovered = DiscoveredObject(
        object_type="table",
        object_name="customers",
        native_name="analytics.sales.customers",
        catalog_name="analytics",
        schema_name="sales",
    )

    db = MagicMock()
    db.scalar.return_value = None
    db.scalars.return_value.all.return_value = []

    result = persist_discovered_object(
        db,
        data_source,
        discovered,
    )

    statement = db.scalar.call_args.args[0]
    compiled = statement.compile()
    sql = str(compiled)
    values = compiled.params.values()

    assert "source_objects.data_source_id" in sql
    assert "source_objects.catalog_name" in sql
    assert "source_objects.schema_name" in sql
    assert "source_objects.object_name" in sql

    assert data_source_id in values
    assert "analytics" in values
    assert "sales" in values
    assert "customers" in values

    assert result.catalog_name == "analytics"
    assert result.schema_name == "sales"
    assert result.object_name == "customers"
