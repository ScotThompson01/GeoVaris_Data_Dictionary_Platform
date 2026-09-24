from unittest.mock import MagicMock, patch

import pyodbc
import pytest

from app.connectors.database.base import (
    DatabaseConnectionConfig,
)
from app.connectors.database.sqlserver_connector import (
    SQLServerConnector,
)


def test_sqlserver_connector_metadata():
    connector = SQLServerConnector()

    assert connector.connector_name == "sqlserver"
    assert connector.connector_version == "0.2.0"
    assert (
        connector.odbc_driver
        == "ODBC Driver 18 for SQL Server"
    )


def test_sqlserver_connection_string():
    connector = SQLServerConnector()

    config = DatabaseConnectionConfig(
        host="sqlserver.example.internal",
        port=1433,
        database="customer_data",
        username="readonly_user",
    )

    connection_string = connector._connection_string(
        config,
        "test-password",
    )

    assert (
        "DRIVER={ODBC Driver 18 for SQL Server}"
        in connection_string
    )
    assert (
        "SERVER={sqlserver.example.internal,1433}"
        in connection_string
    )
    assert "DATABASE={customer_data}" in connection_string
    assert "UID={readonly_user}" in connection_string
    assert "PWD={test-password}" in connection_string
    assert "ApplicationIntent=ReadOnly" in connection_string
    assert "Encrypt=yes" in connection_string


@patch(
    "app.connectors.database.sqlserver_connector.pyodbc.connect"
)
def test_validate_connection_uses_read_only_connection(
    mock_connect,
):
    cursor = MagicMock()
    cursor.fetchone.return_value = (1,)

    connection = MagicMock()
    connection.cursor.return_value = cursor

    mock_connect.return_value = connection

    config = DatabaseConnectionConfig(
        host="sqlserver.example.internal",
        port=1433,
        database="customer_data",
        username="readonly_user",
    )

    connector = SQLServerConnector()

    connector.validate_connection(
        config,
        "runtime-password",
    )

    mock_connect.assert_called_once()

    call_args = mock_connect.call_args

    connection_string = call_args.args[0]

    assert "ApplicationIntent=ReadOnly" in connection_string
    assert "PWD={runtime-password}" in connection_string

    assert call_args.kwargs["autocommit"] is False
    assert call_args.kwargs["timeout"] == 10

    cursor.execute.assert_any_call(
        "SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED"
    )
    cursor.execute.assert_any_call("SELECT 1")

    cursor.close.assert_called_once()
    connection.close.assert_called_once()


def test_sqlserver_normalize_data_type():
    connector = SQLServerConnector()

    assert connector._normalize_data_type("int") == "integer"
    assert connector._normalize_data_type("bigint") == "integer"

    assert connector._normalize_data_type("decimal") == "decimal"
    assert connector._normalize_data_type("float") == "decimal"

    assert connector._normalize_data_type("bit") == "boolean"

    assert connector._normalize_data_type("date") == "date"
    assert (
        connector._normalize_data_type("datetime2")
        == "datetime"
    )
    assert connector._normalize_data_type("time") == "time"

    assert (
        connector._normalize_data_type("nvarchar")
        == "string"
    )
    assert (
        connector._normalize_data_type("varchar")
        == "string"
    )

    assert (
        connector._normalize_data_type("uniqueidentifier")
        == "uuid"
    )

    assert (
        connector._normalize_data_type("varbinary")
        == "binary"
    )
    assert connector._normalize_data_type("xml") == "xml"

    assert (
        connector._normalize_data_type("geography")
        == "other"
    )


@patch(
    "app.connectors.database.sqlserver_connector.pyodbc.connect"
)
def test_discover_objects_returns_normalized_metadata(
    mock_connect,
):
    cursor = MagicMock()

    cursor.fetchall.side_effect = [
        [
            (
                "dbo",
                "customers",
                "table",
            ),
        ],
        [
            (
                "customer_id",
                1,
                "int",
                None,
                None,
                None,
                False,
                None,
                "Customer identifier",
                True,
                True,
            ),
            (
                "customer_name",
                2,
                "nvarchar",
                200,
                None,
                None,
                True,
                None,
                None,
                False,
                False,
            ),
        ],
    ]

    connection = MagicMock()
    connection.cursor.return_value = cursor

    mock_connect.return_value = connection

    config = DatabaseConnectionConfig(
        host="sqlserver.example.internal",
        port=1433,
        database="customer_data",
        username="readonly_user",
    )

    connector = SQLServerConnector()

    objects = connector.discover_objects(
        config,
        "runtime-password",
    )

    assert len(objects) == 1

    discovered_object = objects[0]

    assert discovered_object.object_type == "table"
    assert discovered_object.object_name == "customers"
    assert discovered_object.schema_name == "dbo"
    assert (
        discovered_object.native_name
        == "dbo.customers"
    )
    assert discovered_object.row_count is None

    assert len(discovered_object.fields) == 2

    customer_id = discovered_object.fields[0]

    assert customer_id.field_name == "customer_id"
    assert customer_id.ordinal_position == 1
    assert customer_id.native_data_type == "int"
    assert (
        customer_id.normalized_data_type
        == "integer"
    )
    assert customer_id.is_nullable is False
    assert customer_id.is_primary_key is True
    assert customer_id.is_unique is True
    assert (
        customer_id.source_comment
        == "Customer identifier"
    )

    customer_name = discovered_object.fields[1]

    assert customer_name.field_name == "customer_name"
    assert (
        customer_name.native_data_type
        == "nvarchar"
    )
    assert (
        customer_name.normalized_data_type
        == "string"
    )
    assert customer_name.max_length == 200
    assert customer_name.is_nullable is True

    cursor.close.assert_called_once()
    connection.close.assert_called_once()


@patch(
    "app.connectors.database.sqlserver_connector.pyodbc.connect"
)
def test_discover_objects_wraps_pyodbc_errors(
    mock_connect,
):
    mock_connect.side_effect = pyodbc.Error(
        "test database failure"
    )

    config = DatabaseConnectionConfig(
        host="sqlserver.example.internal",
        port=1433,
        database="customer_data",
        username="readonly_user",
    )

    connector = SQLServerConnector()

    with pytest.raises(
        ConnectionError,
        match="Unable to discover SQL Server metadata.",
    ):
        connector.discover_objects(
            config,
            "runtime-password",
        )

def test_sqlserver_connection_string_escapes_password():
    connector = SQLServerConnector()
    config = DatabaseConnectionConfig(
        host="sqlserver.example.internal",
        port=1433,
        database="customer_data",
        username="readonly_user",
    )

    connection_string = connector._connection_string(
        config,
        "dummy;password}value",
    )

    assert "PWD={dummy;password}}value}" in connection_string
    assert "Encrypt=yes" in connection_string
