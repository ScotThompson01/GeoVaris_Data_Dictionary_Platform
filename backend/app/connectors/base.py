from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DiscoveredField:
    """Normalized technical metadata for one discovered field."""

    field_name: str
    ordinal_position: int
    native_data_type: str | None = None
    normalized_data_type: str | None = None
    max_length: int | None = None
    numeric_precision: int | None = None
    numeric_scale: int | None = None
    is_nullable: bool | None = None
    is_primary_key: bool = False
    is_unique: bool = False
    source_comment: str | None = None


@dataclass(frozen=True)
class DiscoveredObject:
    """Normalized technical metadata for one discovered source object."""

    object_type: str
    object_name: str
    native_name: str
    row_count: int | None = None
    fields: list[DiscoveredField] = field(default_factory=list)


class BaseConnector(ABC):
    """Base interface implemented by GeoVaris source connectors."""

    connector_name: str
    connector_version: str

    @abstractmethod
    def validate(self, source: Path) -> None:
        """Validate that the connector can safely inspect the source."""

    @abstractmethod
    def discover(self, source: Path) -> DiscoveredObject:
        """Discover and return normalized technical metadata."""