"""Read-only aggregate profiling for PostgreSQL fields."""

import psycopg
from psycopg import sql

from app.connectors.database.base import DatabaseConnectionConfig
from app.profiling.database_profile import DatabaseFieldProfile


def profile_postgresql_field(
    *,
    config: DatabaseConnectionConfig,
    schema_name: str,
    object_name: str,
    field_name: str,
    include_distinct: bool = False,
    password: str | None = None,
    statement_timeout_ms: int = 30000,
    ssl_root_cert: str | None = None,
) -> DatabaseFieldProfile:
    """Calculate observed field statistics using source-side aggregates."""

    if not all((schema_name, object_name, field_name)):
        raise ValueError("Schema, object, and field names are required.")

    if not 1 <= statement_timeout_ms <= 300000:
        raise ValueError("Invalid statement timeout.")

    field = sql.Identifier(field_name)
    table = sql.Identifier(schema_name, object_name)

    distinct_expression = (
        sql.SQL("COUNT(DISTINCT {field})").format(field=field)
        if include_distinct
        else sql.SQL("NULL::bigint")
    )

    query = sql.SQL(
        """
        SELECT
            COUNT(*) AS row_count,
            COUNT(*) FILTER (
                WHERE {field} IS NULL
            ) AS null_count,
            {distinct_expression} AS distinct_count
        FROM {table}
        """
    ).format(
        field=field,
        table=table,
        distinct_expression=distinct_expression,
    )

    try:
        from app.connectors.database.postgresql_connector import (
            PostgreSQLConnector,
        )

        connection_options = PostgreSQLConnector()._connection_options(
            config,
            password,
            ssl_root_cert=ssl_root_cert,
        )

        with psycopg.connect(**connection_options) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")

                cursor.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    (str(statement_timeout_ms),),
                )

                cursor.execute(query)
                result = cursor.fetchone()

        if result is None:
            raise RuntimeError("Profiling returned no result.")

        return DatabaseFieldProfile(
            schema_name=schema_name,
            object_name=object_name,
            field_name=field_name,
            row_count=int(result[0]),
            null_count=int(result[1]),
            distinct_count=(
                int(result[2])
                if result[2] is not None
                else None
            ),
        )

    except psycopg.Error:
        raise ConnectionError(
            "PostgreSQL field profiling failed."
        ) from None
