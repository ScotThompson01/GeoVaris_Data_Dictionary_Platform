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


def test_rescan_preserves_existing_field_identity():
    from app.connectors.base import DiscoveredField
    from app.models.data_field import DataField
    from app.models.source_object import SourceObject

    source_id = uuid.uuid4()
    object_id = uuid.uuid4()
    field_id = uuid.uuid4()

    data_source = DataSource(
        id=source_id,
        project_id=uuid.uuid4(),
        name="Synthetic PostgreSQL",
        source_type="postgresql",
        connection_mode="database",
        is_active=True,
    )

    existing_object = SourceObject(
        id=object_id,
        data_source_id=source_id,
        object_type="table",
        object_name="customers",
        native_name="public.customers",
        schema_name="public",
    )

    existing_field = DataField(
        id=field_id,
        source_object_id=object_id,
        field_name="customer_id",
        ordinal_position=2,
        native_data_type="varchar",
        is_nullable=True,
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
                native_data_type="integer",
                normalized_data_type="integer",
                is_nullable=False,
                is_primary_key=True,
            )
        ],
    )

    db = MagicMock()
    db.scalar.return_value = existing_object
    db.scalars.return_value.all.return_value = [existing_field]

    result = persist_discovered_object(db, data_source, discovered)

    assert result is existing_object
    assert existing_field.id == field_id
    assert existing_field.source_object_id == object_id
    assert existing_field.ordinal_position == 1
    assert existing_field.native_data_type == "integer"
    assert existing_field.normalized_data_type == "integer"
    assert existing_field.is_nullable is False
    assert existing_field.is_primary_key is True
    db.add.assert_not_called()
    db.flush.assert_called_once()
