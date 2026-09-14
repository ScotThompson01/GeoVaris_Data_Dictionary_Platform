import psycopg

from app.connectors.database.base import (
    BaseDatabaseConnector,
    DatabaseConnectionConfig,
)
from app.connectors.base import DiscoveredObject


class PostgreSQLConnector(BaseDatabaseConnector):
    """
    Read-only PostgreSQL connector.

    Credentials are supplied at runtime and are never stored by
    the connector.
    """

    connector_name = "postgresql"
    connector_version = "0.1.0"

    def validate_connection(
        self,
        config: DatabaseConnectionConfig,
        password: str | None = None,
    ) -> None:
        """
        Validate PostgreSQL connectivity using a read-only session.

        No source objects or source data are modified.
        """

        connection_options = {
            "host": config.host,
            "port": config.port,
            "dbname": config.database,
            "user": config.username,
            "password": password,
            "connect_timeout": config.connect_timeout_seconds,

            # Enforce read-only transactions at the PostgreSQL
            # session level.
            "options": "-c default_transaction_read_only=on",
        }

        if config.ssl_mode:
            connection_options["sslmode"] = config.ssl_mode

        try:
            with psycopg.connect(
                **connection_options,
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")

                    result = cursor.fetchone()

                    if result is None or result[0] != 1:
                        raise ConnectionError(
                            "PostgreSQL validation query failed."
                        )

        except psycopg.Error as exc:
            # Do not include credentials or the full connection
            # configuration in the exposed error message.
            raise ConnectionError(
                "Unable to validate the PostgreSQL connection."
            ) from exc

    def discover_objects(
        self,
        config: DatabaseConnectionConfig,
        password: str | None = None,
    ) -> list[DiscoveredObject]:
        """
        PostgreSQL object discovery will be implemented in the
        next development increment.
        """

        raise NotImplementedError(
            "PostgreSQL object discovery is not implemented yet."
        )