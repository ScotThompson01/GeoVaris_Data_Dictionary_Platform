import pyodbc

from app.connectors.base import (
    DiscoveredField,
    DiscoveredObject,
)
from app.connectors.database.base import (
    BaseDatabaseConnector,
    DatabaseConnectionConfig,
)


class SQLServerConnector(BaseDatabaseConnector):
    """Read-only Microsoft SQL Server metadata connector."""

    connector_name = "sqlserver"
    connector_version = "0.2.0"

    odbc_driver = "ODBC Driver 18 for SQL Server"

    def _connection_string(
        self,
        config: DatabaseConnectionConfig,
        password: str | None,
    ) -> str:
        """
        Build the runtime SQL Server ODBC connection string.

        Credentials are supplied at runtime and must not be
        persisted or logged.
        """

        def odbc_value(value: str) -> str:
            return "{" + value.replace("}", "}}") + "}"

        parts = [
            f"DRIVER={odbc_value(self.odbc_driver)}",
            f"SERVER={odbc_value(f'{config.host},{config.port}')}",
            f"DATABASE={odbc_value(config.database)}",
            f"UID={odbc_value(config.username or '')}",
            f"PWD={odbc_value(password or '')}",
            "ApplicationIntent=ReadOnly",
        ]

        if config.ssl_mode == "disable":
            parts.extend(
                [
                    "Encrypt=no",
                    "TrustServerCertificate=yes",
                ]
            )
        else:
            parts.append("Encrypt=yes")

        return ";".join(parts)

    def validate_connection(
        self,
        config: DatabaseConnectionConfig,
        password: str | None = None,
    ) -> None:
        """
        Validate SQL Server connectivity using a read-only
        connection and a non-mutating query.
        """

        try:
            connection = pyodbc.connect(
                self._connection_string(
                    config,
                    password,
                ),
                timeout=config.connect_timeout_seconds,
                autocommit=False,
            )

            try:
                cursor = connection.cursor()

                try:
                    cursor.execute(
                        "SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED"
                    )
                    cursor.execute("SELECT 1")

                    result = cursor.fetchone()

                    if result is None or result[0] != 1:
                        raise ConnectionError(
                            "SQL Server validation query failed."
                        )

                finally:
                    cursor.close()

            finally:
                connection.close()

        except pyodbc.Error as exc:
            raise ConnectionError(
                "Unable to validate the SQL Server connection."
            ) from None

    def discover_objects(
        self,
        config: DatabaseConnectionConfig,
        password: str | None = None,
    ) -> list[DiscoveredObject]:
        """
        Discover accessible SQL Server tables and views.

        Discovery uses SQL Server catalog metadata only and does
        not modify source records.
        """

        try:
            connection = pyodbc.connect(
                self._connection_string(
                    config,
                    password,
                ),
                timeout=config.connect_timeout_seconds,
                autocommit=False,
            )

            try:
                cursor = connection.cursor()

                try:
                    cursor.execute(
                        "SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED"
                    )

                    cursor.execute(
                        """
                        SELECT
                            s.name AS schema_name,
                            o.name AS object_name,
                            CASE o.type
                                WHEN 'U' THEN 'table'
                                WHEN 'V' THEN 'view'
                            END AS object_type
                        FROM sys.objects AS o
                        JOIN sys.schemas AS s
                            ON s.schema_id = o.schema_id
                        WHERE o.type IN ('U', 'V')
                          AND o.is_ms_shipped = 0
                        ORDER BY
                            s.name,
                            o.name
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

                finally:
                    cursor.close()

            finally:
                connection.close()

        except pyodbc.Error as exc:
            raise ConnectionError(
                "Unable to discover SQL Server metadata."
            ) from None

    def _discover_fields(
        self,
        cursor,
        schema_name: str,
        object_name: str,
    ) -> list[DiscoveredField]:
        """
        Discover normalized column metadata for one SQL Server
        table or view.
        """

        cursor.execute(
            """
            SELECT
                c.name AS field_name,
                c.column_id AS ordinal_position,
                t.name AS native_data_type,

                CASE
                    WHEN c.max_length = -1 THEN NULL
                    WHEN t.name IN ('nvarchar', 'nchar')
                        THEN c.max_length / 2
                    WHEN t.name IN (
                        'varchar',
                        'char',
                        'varbinary',
                        'binary'
                    )
                        THEN c.max_length
                    ELSE NULL
                END AS max_length,

                CASE
                    WHEN t.name IN (
                        'decimal',
                        'numeric'
                    )
                        THEN c.precision
                    ELSE NULL
                END AS numeric_precision,

                CASE
                    WHEN t.name IN (
                        'decimal',
                        'numeric'
                    )
                        THEN c.scale
                    ELSE NULL
                END AS numeric_scale,

                c.is_nullable,

                OBJECT_DEFINITION(c.default_object_id)
                    AS default_value,

                CAST(
                    ep.value AS nvarchar(4000)
                ) AS source_comment,

                CASE
                    WHEN pk.column_id IS NOT NULL
                        THEN CAST(1 AS bit)
                    ELSE CAST(0 AS bit)
                END AS is_primary_key,

                CASE
                    WHEN uq.column_id IS NOT NULL
                        THEN CAST(1 AS bit)
                    ELSE CAST(0 AS bit)
                END AS is_unique

            FROM sys.columns AS c

            JOIN sys.objects AS o
                ON o.object_id = c.object_id

            JOIN sys.schemas AS s
                ON s.schema_id = o.schema_id

            JOIN sys.types AS t
                ON t.user_type_id = c.user_type_id

            LEFT JOIN sys.extended_properties AS ep
                ON ep.major_id = c.object_id
               AND ep.minor_id = c.column_id
               AND ep.name = 'MS_Description'

            LEFT JOIN (
                SELECT
                    ic.object_id,
                    ic.column_id
                FROM sys.indexes AS i
                JOIN sys.index_columns AS ic
                    ON ic.object_id = i.object_id
                   AND ic.index_id = i.index_id
                WHERE i.is_primary_key = 1
            ) AS pk
                ON pk.object_id = c.object_id
               AND pk.column_id = c.column_id

            LEFT JOIN (
                SELECT
                    ic.object_id,
                    ic.column_id
                FROM sys.indexes AS i
                JOIN sys.index_columns AS ic
                    ON ic.object_id = i.object_id
                   AND ic.index_id = i.index_id
                WHERE i.is_unique = 1
            ) AS uq
                ON uq.object_id = c.object_id
               AND uq.column_id = c.column_id

            WHERE s.name = ?
              AND o.name = ?
              AND o.type IN ('U', 'V')

            ORDER BY c.column_id
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
                    is_nullable=bool(is_nullable),
                    is_primary_key=bool(is_primary_key),
                    is_unique=bool(is_unique),
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
            "tinyint",
            "smallint",
            "int",
            "bigint",
        }:
            return "integer"

        if value in {
            "decimal",
            "numeric",
            "money",
            "smallmoney",
            "float",
            "real",
        }:
            return "decimal"

        if value == "bit":
            return "boolean"

        if value == "date":
            return "date"

        if value in {
            "datetime",
            "datetime2",
            "smalldatetime",
            "datetimeoffset",
        }:
            return "datetime"

        if value == "time":
            return "time"

        if value in {
            "char",
            "varchar",
            "text",
            "nchar",
            "nvarchar",
            "ntext",
            "sysname",
        }:
            return "string"

        if value == "uniqueidentifier":
            return "uuid"

        if value in {
            "binary",
            "varbinary",
            "image",
            "rowversion",
            "timestamp",
        }:
            return "binary"

        if value == "xml":
            return "xml"

        return "other"