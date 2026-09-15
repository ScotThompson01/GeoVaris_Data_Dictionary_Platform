from unittest.mock import MagicMock, patch

from app.connectors.database.base import DatabaseConnectionConfig
from app.connectors.database.postgresql_connector import (
    PostgreSQLConnector,
)


def test_postgresql_connector_metadata():
    connector = PostgreSQLConnector()

    assert connector.connector_name == "postgresql"
    assert connector.connector_version == "0.2.0"


@patch(
    "app.connectors.database.postgresql_connector.psycopg.connect"
)
def test_validate_connection_uses_read_only_session(
    mock_connect,
):
    cursor = MagicMock()
    cursor.fetchone.return_value = (1,)

    cursor_context = MagicMock()
    cursor_context.__enter__.return_value = cursor

    connection = MagicMock()
    connection.cursor.return_value = cursor_context

    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection

    mock_connect.return_value = connection_context

    config = DatabaseConnectionConfig(
        host="database.example.internal",
        port=5432,
        database="customer_data",
        username="readonly_user",
    )

    connector = PostgreSQLConnector()

    connector.validate_connection(
        config=config,
        password="test-password",
    )

    mock_connect.assert_called_once()

    kwargs = mock_connect.call_args.kwargs

    assert kwargs["host"] == "database.example.internal"
    assert kwargs["port"] == 5432
    assert kwargs["dbname"] == "customer_data"
    assert kwargs["user"] == "readonly_user"

    assert (
        kwargs["options"]
        == "-c default_transaction_read_only=on"
    )

    cursor.execute.assert_called_once_with("SELECT 1")


def test_postgresql_type_normalization():
    connector = PostgreSQLConnector()

    assert connector._normalize_data_type("integer") == "integer"
    assert connector._normalize_data_type("bigint") == "integer"

    assert (
        connector._normalize_data_type("numeric(12,2)")
        == "decimal"
    )

    assert connector._normalize_data_type("boolean") == "boolean"
    assert connector._normalize_data_type("date") == "date"

    assert (
        connector._normalize_data_type(
            "timestamp with time zone"
        )
        == "datetime"
    )

    assert (
        connector._normalize_data_type(
            "character varying(255)"
        )
        == "string"
    )

    assert connector._normalize_data_type("uuid") == "uuid"
    assert connector._normalize_data_type("jsonb") == "json"


def test_unknown_postgresql_type_normalizes_to_other():
    connector = PostgreSQLConnector()

    assert (
        connector._normalize_data_type(
            "some_future_postgresql_type"
        )
        == "other"
    )


def test_discover_fields_maps_postgresql_metadata():
    connector = PostgreSQLConnector()

    cursor = MagicMock()

    cursor.fetchall.return_value = [
        (
            "amount",
            3,
            "numeric(12,2)",
            None,
            12,
            2,
            False,
            "0",
            "Transaction amount",
            False,
            False,
        ),
    ]

    fields = connector._discover_fields(
        cursor=cursor,
        schema_name="public",
        object_name="transactions",
    )

    assert len(fields) == 1

    field = fields[0]

    assert field.field_name == "amount"
    assert field.ordinal_position == 3

    assert field.native_data_type == "numeric(12,2)"
    assert field.normalized_data_type == "decimal"

    assert field.max_length is None
    assert field.numeric_precision == 12
    assert field.numeric_scale == 2

    assert field.is_nullable is False
    assert field.is_primary_key is False
    assert field.is_unique is False

    assert field.default_value == "0"

    assert (
        field.source_comment
        == "Transaction amount"
    )


def test_discover_fields_maps_character_length():
    connector = PostgreSQLConnector()

    cursor = MagicMock()

    cursor.fetchall.return_value = [
        (
            "customer_name",
            2,
            "character varying(255)",
            255,
            None,
            None,
            True,
            None,
            "Customer display name",
            False,
            False,
        ),
    ]

    fields = connector._discover_fields(
        cursor=cursor,
        schema_name="public",
        object_name="customers",
    )

    assert len(fields) == 1

    field = fields[0]

    assert field.field_name == "customer_name"
    assert field.ordinal_position == 2

    assert (
        field.native_data_type
        == "character varying(255)"
    )
    assert field.normalized_data_type == "string"

    assert field.max_length == 255
    assert field.numeric_precision is None
    assert field.numeric_scale is None

    assert field.is_nullable is True
    assert field.default_value is None

    assert (
        field.source_comment
        == "Customer display name"
    )