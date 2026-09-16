import pyodbc

from app.connectors.base import DiscoveredObject
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

        parts = [
            f"DRIVER={{{self.odbc_driver}}}",
            f"SERVER={config.host},{config.port}",
            f"DATABASE={config.database}",
            f"UID={config.username or ''}",
            f"PWD={password or ''}",
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
            ) from exc

    def discover_objects(
        self,
        config: DatabaseConnectionConfig,
        password: str | None = None,
    ) -> list[DiscoveredObject]:
        """
        SQL Server object discovery will be implemented in the
        next database-discovery increment.
        """

        raise NotImplementedError(
            "SQL Server metadata discovery is not implemented yet."
        )
        