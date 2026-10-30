"""Tests for read-only PostgreSQL Data Quality range measurement."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.connectors.database.base import DatabaseConnectionConfig
from app.connectors.database.postgresql_connector import PostgreSQLConnector


@patch("app.connectors.database.postgresql_range_measurement.psycopg.connect")
def test_measure_range_returns_aggregate_counts(mock_connect):
    cursor = MagicMock()
    cursor.fetchone.return_value = (100, 95, 5)

    cursor_context = MagicMock()
    cursor_context.__enter__.return_value = cursor

    connection = MagicMock()
    connection.cursor.return_value = cursor_context

    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection

    mock_connect.return_value = connection_context

    config = DatabaseConnectionConfig(
        host="postgres.internal",
        port=5432,
        database="customer_database",
        username="readonly_user",
    )

    result = PostgreSQLConnector().measure_range(
        config=config,
        schema_name="public",
        object_name="assets",
        field_name="latitude",
        min_value=Decimal("-90"),
        max_value=Decimal("90"),
        null_allowed=True,
        password="runtime-only-password",
    )

    assert result.total_count == 100
    assert result.passing_count == 95
    assert result.violation_count == 5

    assert cursor.execute.call_count == 2
    cursor.fetchone.assert_called_once()
    cursor.fetchall.assert_not_called()
    mock_connect.assert_called_once()


@patch("app.connectors.database.postgresql_range_measurement.psycopg.connect")
def test_measure_range_uses_safe_identifiers_and_parameters(mock_connect):
    from psycopg import sql

    cursor = MagicMock()
    cursor.fetchone.return_value = (10, 8, 2)

    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    mock_connect.return_value.__enter__.return_value = connection

    config = DatabaseConnectionConfig(
        host="postgres.internal",
        port=5432,
        database="customer_database",
        username="readonly_user",
    )

    PostgreSQLConnector().measure_range(
        config=config,
        schema_name="public",
        object_name="assets",
        field_name='latitude"; DROP TABLE assets; --',
        min_value=Decimal("-90"),
        max_value=Decimal("90"),
        null_allowed=False,
        statement_timeout_ms=5000,
    )

    connection_options = mock_connect.call_args.kwargs

    assert connection_options["options"] == (
        "-c default_transaction_read_only=on"
    )

    assert cursor.execute.call_count == 2

    timeout_call = cursor.execute.call_args_list[0]
    assert timeout_call.args[1] == ("5000",)

    measurement_call = cursor.execute.call_args_list[1]
    query = measurement_call.args[0]

    assert isinstance(query, sql.Composable)
    assert measurement_call.args[1] == (
        Decimal("-90"),
        Decimal("90"),
        Decimal("-90"),
        Decimal("90"),
    )
    assert query.as_string().count("%s") == len(measurement_call.args[1])

    assert any(
        isinstance(part, sql.Identifier)
        for part in query._obj
        if isinstance(query, sql.Composed)
    )

import pytest


@pytest.mark.parametrize(
    ("null_allowed", "expected_null_condition"),
    [
        (True, "IS NULL"),
        (False, "IS NOT NULL"),
    ],
)
@patch("app.connectors.database.postgresql_range_measurement.psycopg.connect")
def test_measure_range_null_handling(
    mock_connect, null_allowed, expected_null_condition
):
    cursor = MagicMock()
    cursor.fetchone.return_value = (10, 8, 2)

    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    mock_connect.return_value.__enter__.return_value = connection

    config = DatabaseConnectionConfig(
        host="postgres.internal",
        port=5432,
        database="customer_database",
        username="readonly_user",
    )

    PostgreSQLConnector().measure_range(
        config=config,
        schema_name="public",
        object_name="assets",
        field_name="latitude",
        min_value=Decimal("-90"),
        max_value=Decimal("90"),
        null_allowed=null_allowed,
    )

    query = cursor.execute.call_args_list[1].args[0]

    assert expected_null_condition in str(query)
    assert cursor.execute.call_args_list[1].args[1] == (
        Decimal("-90"),
        Decimal("90"),
        Decimal("-90"),
        Decimal("90"),
    )

@patch("app.connectors.database.postgresql_range_measurement.psycopg.connect")
def test_measure_range_rejects_invalid_bounds_without_connecting(mock_connect):
    config = DatabaseConnectionConfig(
        host="postgres.internal",
        port=5432,
        database="customer_database",
        username="readonly_user",
    )

    with pytest.raises(ValueError, match="Minimum cannot exceed maximum"):
        PostgreSQLConnector().measure_range(
            config=config,
            schema_name="public",
            object_name="assets",
            field_name="latitude",
            min_value=Decimal("90"),
            max_value=Decimal("-90"),
            null_allowed=False,
        )

    mock_connect.assert_not_called()

@pytest.mark.parametrize("timeout_ms", [0, -1, 300001])
@patch("app.connectors.database.postgresql_range_measurement.psycopg.connect")
def test_measure_range_rejects_invalid_timeout_without_connecting(
    mock_connect, timeout_ms
):
    config = DatabaseConnectionConfig(
        host="postgres.internal",
        port=5432,
        database="customer_database",
        username="readonly_user",
    )

    with pytest.raises(ValueError, match="Statement timeout"):
        PostgreSQLConnector().measure_range(
            config=config,
            schema_name="public",
            object_name="assets",
            field_name="latitude",
            min_value=Decimal("-90"),
            max_value=Decimal("90"),
            null_allowed=False,
            statement_timeout_ms=timeout_ms,
        )

    mock_connect.assert_not_called()

@patch("app.connectors.database.postgresql_range_measurement.psycopg.connect")
def test_measure_range_sanitizes_postgresql_errors(mock_connect):
    import psycopg

    mock_connect.side_effect = psycopg.OperationalError(
        "Connection failed: password=secret-value host=postgres.internal"
    )

    config = DatabaseConnectionConfig(
        host="postgres.internal",
        port=5432,
        database="customer_database",
        username="readonly_user",
    )

    with pytest.raises(
        ConnectionError,
        match="PostgreSQL range measurement failed",
    ) as error:
        PostgreSQLConnector().measure_range(
            config=config,
            schema_name="public",
            object_name="assets",
            field_name="latitude",
            min_value=Decimal("-90"),
            max_value=Decimal("90"),
            null_allowed=False,
            password="secret-value",
        )

    assert "secret-value" not in str(error.value)
    assert "postgres.internal" not in str(error.value)
    assert error.value.__cause__ is None
