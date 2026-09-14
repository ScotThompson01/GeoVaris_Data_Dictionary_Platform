from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.connectors.base import DiscoveredObject


@dataclass(frozen=True)
class DatabaseConnectionConfig:
    """
    Non-secret database connection metadata.

    Credentials are intentionally not stored in this object.
    Secret handling will be supplied separately through the
    deployment/runtime environment.
    """

    host: str
    port: int
    database: str

    username: str | None = None

    connect_timeout_seconds: int = 10

    ssl_mode: str | None = None


class BaseDatabaseConnector(ABC):
    """
    Base interface for relational database connectors.

    Implementations must use read-only access whenever possible
    and return normalized GeoVaris discovery metadata.
    """

    connector_name: str
    connector_version: str

    @abstractmethod
    def validate_connection(
        self,
        config: DatabaseConnectionConfig,
        password: str | None = None,
    ) -> None:
        """
        Validate that GeoVaris can establish a connection.

        Implementations must not modify source data.
        """

    @abstractmethod
    def discover_objects(
        self,
        config: DatabaseConnectionConfig,
        password: str | None = None,
    ) -> list[DiscoveredObject]:
        """
        Discover supported source objects and fields.

        Implementations should return normalized metadata only.
        """