from unittest.mock import MagicMock, patch

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
        "SERVER=sqlserver.example.internal,1433"
        in connection_string
    )
    assert "DATABASE=customer_data" in connection_string
    assert "UID=readonly_user" in connection_string
    assert "PWD=test-password" in connection_string
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
    assert "PWD=runtime-password" in connection_string

    assert call_args.kwargs["autocommit"] is False
    assert call_args.kwargs["timeout"] == 10

    cursor.execute.assert_any_call(
        "SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED"
    )
    cursor.execute.assert_any_call("SELECT 1")

    cursor.close.assert_called_once()
    connection.close.assert_called_once()


def test_discover_objects_not_implemented():
    connector = SQLServerConnector()

    config = DatabaseConnectionConfig(
        host="sqlserver.example.internal",
        port=1433,
        database="customer_data",
        username="readonly_user",
    )

    with pytest.raises(NotImplementedError):
        connector.discover_objects(
            config,
            "runtime-password",
        )