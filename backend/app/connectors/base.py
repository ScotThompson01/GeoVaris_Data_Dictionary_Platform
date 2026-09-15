from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DiscoveredField:
    """
    Normalized technical metadata for one discovered field.

    Connector implementations should populate only metadata that
    can be determined from the source. Unknown or unsupported
    attributes should remain None.
    """

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

    default_value: str | None = None
    source_comment: str | None = None


@dataclass(frozen=True)
class DiscoveredObject:
    """
    Normalized technical metadata for one discovered source object.

    Examples include files, database tables, database views,
    worksheets, and other connector-supported objects.
    """

    object_type: str
    object_name: str
    native_name: str

    schema_name: str | None = None
    row_count: int | None = None

    fields: list[DiscoveredField] = field(
        default_factory=list,
    )


class BaseConnector(ABC):
    """
    Base interface for file-oriented GeoVaris connectors.

    Connectors must inspect sources without modifying source data.
    """

    connector_name: str
    connector_version: str

    @abstractmethod
    def validate(
        self,
        source: Path,
    ) -> None:
        """
        Validate that the connector can safely inspect the source.
        """

    @abstractmethod
    def discover(
        self,
        source: Path,
    ) -> DiscoveredObject:
        """
        Discover technical metadata and return it using the
        normalized GeoVaris discovery model.
        """