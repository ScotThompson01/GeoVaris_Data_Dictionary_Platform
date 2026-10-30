"""Isolated tests for Data Quality range measurement orchestration."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from app.connectors.database.base import DatabaseConnectionConfig
from app.connectors.database.postgresql_range_measurement import RangeMeasurement
from app.services.data_quality_rule_execution import measure_prepared_range_rule


def test_measurement_uses_approved_rule_values_and_source_metadata():
    config = DatabaseConnectionConfig(
        host="example.invalid",
        port=5432,
        database="test_database",
        username="readonly_user",
    )
    prepared = {
        "version": SimpleNamespace(
            min_value=Decimal("24.3"),
            max_value=Decimal("31.1"),
            null_allowed=False,
        ),
        "field": SimpleNamespace(field_name="latitude"),
        "source_object": SimpleNamespace(
            schema_name="public",
            object_name="locations",
        ),
    }
    expected = RangeMeasurement(
        total_count=100,
        passing_count=95,
        violation_count=5,
    )
    connector = Mock()
    connector.measure_range.return_value = expected

    result = measure_prepared_range_rule(
        prepared,
        config=config,
        password="runtime_test_secret",
        connector=connector,
        statement_timeout_ms=5000,
    )

    assert result == expected
    connector.measure_range.assert_called_once_with(
        config=config,
        schema_name="public",
        object_name="locations",
        field_name="latitude",
        min_value=Decimal("24.3"),
        max_value=Decimal("31.1"),
        null_allowed=False,
        password="runtime_test_secret",
        statement_timeout_ms=5000,
    )
