from unittest.mock import MagicMock, patch

import pytest

from app.connectors.database.base import DatabaseConnectionConfig
from app.connectors.database.postgresql_connector import (
    PostgreSQLConnector,
)


def test_postgresql_connector_metadata():
    connector = PostgreSQLConnector()

    assert connector.connector_name == "postgresql"
    assert connector.connector_version == "0.1.0"


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

    cursor.execute.assert_called_once_with(
        "SELECT 1"
    )


def test_discover_objects_not_implemented_yet():
    connector = PostgreSQLConnector()

    config = DatabaseConnectionConfig(
        host="localhost",
        port=5432,
        database="example",
    )

    with pytest.raises(
        NotImplementedError,
        match="object discovery",
    ):
        connector.discover_objects(config)