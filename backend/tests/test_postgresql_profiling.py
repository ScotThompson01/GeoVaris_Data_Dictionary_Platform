"""Offline regression tests for PostgreSQL field profiling."""

from decimal import Decimal
from unittest.mock import patch

import pytest
import psycopg

from app.connectors.database.base import DatabaseConnectionConfig
from app.connectors.database.postgresql_connector import PostgreSQLConnector
from app.profiling.database_profile import DatabaseFieldProfile


def make_profile(
    row_count: int,
    null_count: int,
    distinct_count: int | None = None,
) -> DatabaseFieldProfile:
    return DatabaseFieldProfile(
        schema_name="public",
        object_name="synthetic_customers",
        field_name="customer_id",
        row_count=row_count,
        null_count=null_count,
        distinct_count=distinct_count,
    )


def test_profile_calculates_observed_statistics() -> None:
    profile = make_profile(10000, 150, 9720)

    assert profile.populated_count == 9850
    assert profile.null_percentage == Decimal("1.5000")
    assert profile.completeness_percentage == Decimal("98.5000")
    assert profile.distinct_percentage == Decimal("97.2000")


def test_empty_profile_is_not_falsely_scored() -> None:
    profile = make_profile(0, 0)

    assert profile.null_percentage is None
    assert profile.completeness_percentage is None
    assert profile.distinct_percentage is None


def test_unmeasured_distinct_count_remains_unknown() -> None:
    profile = make_profile(100, 5)

    assert profile.distinct_count is None
    assert profile.distinct_percentage is None
    assert profile.completeness_percentage == Decimal("95.0000")


@pytest.mark.parametrize(
    ("rows", "nulls", "distinct"),
    [
        (-1, 0, None),
        (100, -1, None),
        (100, 101, None),
        (100, 20, 90),
        (100, 20, -1),
    ],
)
def test_invalid_counts_are_rejected(
    rows: int,
    nulls: int,
    distinct: int | None,
) -> None:
    with pytest.raises(ValueError):
        make_profile(rows, nulls, distinct)


def test_connector_uses_read_only_aggregate_query() -> None:
    config = DatabaseConnectionConfig(
        host="synthetic.invalid",
        port=5432,
        database="synthetic",
        username="synthetic",
    )

    with patch(
        "app.connectors.database.postgresql_profiling.psycopg.connect"
    ) as connect:
        connection = connect.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (1000, 25, None)

        result = PostgreSQLConnector().profile_field(
            config=config,
            schema_name="public",
            object_name="synthetic_customers",
            field_name="customer_id",
        )

        assert result.row_count == 1000
        assert result.null_count == 25
        assert result.distinct_count is None
        assert result.completeness_percentage == Decimal("97.5000")

        options = connect.call_args.kwargs
        assert "default_transaction_read_only=on" in options["options"]

        calls = cursor.execute.call_args_list
        assert calls[0].args[0] == "SET TRANSACTION READ ONLY"
        assert "statement_timeout" in calls[1].args[0]

        query = calls[2].args[0].as_string()
        assert "COUNT(*)" in query
        assert "IS NULL" in query
        assert '"public"."synthetic_customers"' in query
        assert '"customer_id"' in query
        assert "NULL::bigint" in query


def test_distinct_measurement_is_explicitly_opt_in() -> None:
    config = DatabaseConnectionConfig(
        host="synthetic.invalid",
        port=5432,
        database="synthetic",
        username="synthetic",
    )

    with patch(
        "app.connectors.database.postgresql_profiling.psycopg.connect"
    ) as connect:
        connection = connect.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (100, 5, 80)

        result = PostgreSQLConnector().profile_field(
            config=config,
            schema_name="public",
            object_name="synthetic_customers",
            field_name="customer_id",
            include_distinct=True,
        )

        assert result.distinct_count == 80

        query = cursor.execute.call_args_list[2].args[0].as_string()
        assert "COUNT(DISTINCT" in query


def test_database_errors_are_sanitized() -> None:
    config = DatabaseConnectionConfig(
        host="synthetic.invalid",
        port=5432,
        database="synthetic",
        username="synthetic",
    )

    with patch(
        "app.connectors.database.postgresql_profiling.psycopg.connect",
        side_effect=psycopg.OperationalError("synthetic sensitive detail"),
    ):
        with pytest.raises(
            ConnectionError,
            match="PostgreSQL field profiling failed",
        ) as error:
            PostgreSQLConnector().profile_field(
                config=config,
                schema_name="public",
                object_name="synthetic_customers",
                field_name="customer_id",
            )

    assert "synthetic sensitive detail" not in str(error.value)
