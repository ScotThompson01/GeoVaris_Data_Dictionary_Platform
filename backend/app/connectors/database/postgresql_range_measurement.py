from dataclasses import dataclass
from decimal import Decimal

import psycopg
from psycopg import sql

from app.connectors.database.base import DatabaseConnectionConfig


@dataclass(frozen=True)
class RangeMeasurement:
    total_count: int
    passing_count: int
    violation_count: int


def measure_postgresql_range(
    *,
    config: DatabaseConnectionConfig,
    schema_name: str,
    object_name: str,
    field_name: str,
    min_value: Decimal,
    max_value: Decimal,
    null_allowed: bool,
    password: str | None = None,
    statement_timeout_ms: int = 30000,
) -> RangeMeasurement:
    """Measure one numeric range rule using a read-only aggregate query."""
    if min_value > max_value:
        raise ValueError("Minimum cannot exceed maximum.")

    if not 1 <= statement_timeout_ms <= 300000:
        raise ValueError("Statement timeout must be between 1 and 300000 ms.")

    if not all((schema_name, object_name, field_name)):
        raise ValueError("Schema, object, and field names are required.")

    field = sql.Identifier(field_name)
    table = sql.Identifier(schema_name, object_name)

    if null_allowed:
        passing_condition = sql.SQL(
            "({field} IS NULL OR {field} BETWEEN %s AND %s)"
        ).format(field=field)
    else:
        passing_condition = sql.SQL(
            "({field} IS NOT NULL AND {field} BETWEEN %s AND %s)"
        ).format(field=field)

    query = sql.SQL(
        """
        SELECT
            COUNT(*) AS total_count,
            COUNT(*) FILTER (WHERE {passing}) AS passing_count,
            COUNT(*) - COUNT(*) FILTER (WHERE {passing}) AS violation_count
        FROM {table}
        """
    ).format(
        passing=passing_condition,
        table=table,
    )

    try:
        with psycopg.connect(
            host=config.host,
            port=config.port,
            dbname=config.database,
            user=config.username,
            password=password,
            connect_timeout=config.connect_timeout_seconds,
            options="-c default_transaction_read_only=on",
            **({"sslmode": config.ssl_mode} if config.ssl_mode else {}),
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    (str(statement_timeout_ms),),
                )
                cursor.execute(
                    query,
                    (min_value, max_value, min_value, max_value),
                )
                result = cursor.fetchone()

        if result is None:
            raise RuntimeError("Range measurement returned no result.")

        return RangeMeasurement(
            total_count=int(result[0]),
            passing_count=int(result[1]),
            violation_count=int(result[2]),
        )
    except psycopg.Error:
        raise ConnectionError("PostgreSQL range measurement failed.") from None

