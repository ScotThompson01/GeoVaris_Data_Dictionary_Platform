import psycopg

from app.connectors.base import (
    DiscoveredField,
    DiscoveredObject,
)
from app.connectors.database.base import (
    BaseDatabaseConnector,
    DatabaseConnectionConfig,
)


class PostgreSQLConnector(BaseDatabaseConnector):
    """Read-only PostgreSQL metadata connector."""

    connector_name = "postgresql"
    connector_version = "0.2.0"

    def _connection_options(
        self,
        config: DatabaseConnectionConfig,
        password: str | None,
    ) -> dict:
        options = {
            "host": config.host,
            "port": config.port,
            "dbname": config.database,
            "user": config.username,
            "password": password,
            "connect_timeout": config.connect_timeout_seconds,
            "options": "-c default_transaction_read_only=on",
        }

        if config.ssl_mode:
            options["sslmode"] = config.ssl_mode

        return options

    def validate_connection(
        self,
        config: DatabaseConnectionConfig,
        password: str | None = None,
    ) -> None:
        try:
            with psycopg.connect(
                **self._connection_options(
                    config,
                    password,
                )
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")

                    result = cursor.fetchone()

                    if result is None or result[0] != 1:
                        raise ConnectionError(
                            "PostgreSQL validation query failed."
                        )

        except psycopg.Error as exc:
            raise ConnectionError(
                "Unable to validate the PostgreSQL connection."
            ) from None

    def discover_objects(
        self,
        config: DatabaseConnectionConfig,
        password: str | None = None,
    ) -> list[DiscoveredObject]:
        """
        Discover accessible PostgreSQL tables and views.

        Discovery uses PostgreSQL catalog metadata only.
        Source records are not modified.
        """

        try:
            with psycopg.connect(
                **self._connection_options(
                    config,
                    password,
                )
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            n.nspname AS schema_name,
                            c.relname AS object_name,
                            CASE c.relkind
                                WHEN 'r' THEN 'table'
                                WHEN 'p' THEN 'table'
                                WHEN 'v' THEN 'view'
                                WHEN 'm' THEN 'materialized_view'
                            END AS object_type
                        FROM pg_catalog.pg_class AS c
                        JOIN pg_catalog.pg_namespace AS n
                            ON n.oid = c.relnamespace
                        WHERE c.relkind IN ('r', 'p', 'v', 'm')
                          AND n.nspname NOT IN (
                              'pg_catalog',
                              'information_schema'
                          )
                          AND n.nspname NOT LIKE 'pg_toast%'
                          AND has_schema_privilege(
                              n.oid,
                              'USAGE'
                          )
                        ORDER BY
                            n.nspname,
                            c.relname
                        """
                    )

                    object_rows = cursor.fetchall()

                    discovered_objects: list[
                        DiscoveredObject
                    ] = []

                    for (
                        schema_name,
                        object_name,
                        object_type,
                    ) in object_rows:
                        fields = self._discover_fields(
                            cursor=cursor,
                            schema_name=schema_name,
                            object_name=object_name,
                        )

                        discovered_objects.append(
                            DiscoveredObject(
                                object_type=object_type,
                                object_name=object_name,
                                native_name=(
                                    f"{schema_name}.{object_name}"
                                ),
                                schema_name=schema_name,
                                row_count=None,
                                fields=fields,
                            )
                        )

                    return discovered_objects

        except psycopg.Error as exc:
            raise ConnectionError(
                "Unable to discover PostgreSQL metadata."
            ) from None

    def _discover_fields(
        self,
        cursor,
        schema_name: str,
        object_name: str,
    ) -> list[DiscoveredField]:
        cursor.execute(
            """
            SELECT
                a.attname AS field_name,
                a.attnum AS ordinal_position,

                pg_catalog.format_type(
                    a.atttypid,
                    a.atttypmod
                ) AS native_data_type,

                CASE
                    WHEN a.atttypmod > 4
                     AND t.typname IN ('varchar', 'bpchar')
                    THEN a.atttypmod - 4
                    ELSE NULL
                END AS max_length,

                CASE
                    WHEN t.typname = 'numeric'
                     AND a.atttypmod >= 0
                    THEN (
                        (a.atttypmod - 4) >> 16
                    ) & 65535
                    ELSE NULL
                END AS numeric_precision,

                CASE
                    WHEN t.typname = 'numeric'
                     AND a.atttypmod >= 0
                    THEN (
                        a.atttypmod - 4
                    ) & 65535
                    ELSE NULL
                END AS numeric_scale,

                NOT a.attnotnull AS is_nullable,

                pg_catalog.pg_get_expr(
                    d.adbin,
                    d.adrelid
                ) AS default_value,

                pg_catalog.col_description(
                    a.attrelid,
                    a.attnum
                ) AS source_comment,

                EXISTS (
                    SELECT 1
                    FROM pg_catalog.pg_index AS i
                    WHERE i.indrelid = a.attrelid
                      AND i.indisprimary
                      AND a.attnum = ANY(i.indkey)
                ) AS is_primary_key,

                EXISTS (
                    SELECT 1
                    FROM pg_catalog.pg_index AS i
                    WHERE i.indrelid = a.attrelid
                      AND i.indisunique
                      AND a.attnum = ANY(i.indkey)
                ) AS is_unique

            FROM pg_catalog.pg_attribute AS a

            JOIN pg_catalog.pg_class AS c
                ON c.oid = a.attrelid

            JOIN pg_catalog.pg_namespace AS n
                ON n.oid = c.relnamespace

            JOIN pg_catalog.pg_type AS t
                ON t.oid = a.atttypid

            LEFT JOIN pg_catalog.pg_attrdef AS d
                ON d.adrelid = a.attrelid
               AND d.adnum = a.attnum

            WHERE n.nspname = %s
              AND c.relname = %s
              AND a.attnum > 0
              AND NOT a.attisdropped

            ORDER BY a.attnum
            """,
            (
                schema_name,
                object_name,
            ),
        )

        fields: list[DiscoveredField] = []

        for row in cursor.fetchall():
            (
                field_name,
                ordinal_position,
                native_data_type,
                max_length,
                numeric_precision,
                numeric_scale,
                is_nullable,
                default_value,
                source_comment,
                is_primary_key,
                is_unique,
            ) = row

            fields.append(
                DiscoveredField(
                    field_name=field_name,
                    ordinal_position=ordinal_position,
                    native_data_type=native_data_type,
                    normalized_data_type=(
                        self._normalize_data_type(
                            native_data_type
                        )
                    ),
                    max_length=max_length,
                    numeric_precision=numeric_precision,
                    numeric_scale=numeric_scale,
                    is_nullable=is_nullable,
                    is_primary_key=is_primary_key,
                    is_unique=is_unique,
                    default_value=default_value,
                    source_comment=source_comment,
                )
            )

        return fields

    @staticmethod
    def _normalize_data_type(
        native_data_type: str,
    ) -> str:
        value = native_data_type.lower()

        if value in {
            "smallint",
            "integer",
            "bigint",
        }:
            return "integer"

        if (
            value.startswith("numeric")
            or value.startswith("decimal")
            or value
            in {
                "real",
                "double precision",
            }
        ):
            return "decimal"

        if value == "boolean":
            return "boolean"

        if value == "date":
            return "date"

        if value.startswith("timestamp"):
            return "datetime"

        if value.startswith("time"):
            return "time"

        if (
            value.startswith("character varying")
            or value.startswith("character(")
            or value
            in {
                "text",
                "name",
            }
        ):
            return "string"

        if value == "uuid":
            return "uuid"

        if value in {
            "json",
            "jsonb",
        }:
            return "json"

        if value == "bytea":
            return "binary"

        return "other"