"""Normalized aggregate profiling results for relational databases."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class DatabaseFieldProfile:
    """Observed field statistics without raw source records."""

    schema_name: str
    object_name: str
    field_name: str

    row_count: int
    null_count: int

    distinct_count: int | None = None

    minimum_value: str | None = None
    maximum_value: str | None = None

    minimum_length: int | None = None
    maximum_length: int | None = None

    def __post_init__(self) -> None:
        if self.row_count < 0:
            raise ValueError("Row count cannot be negative.")

        if not 0 <= self.null_count <= self.row_count:
            raise ValueError("Invalid null count.")

        if self.distinct_count is not None:
            if not 0 <= self.distinct_count <= self.populated_count:
                raise ValueError("Invalid distinct count.")

    @property
    def populated_count(self) -> int:
        return self.row_count - self.null_count

    @property
    def null_percentage(self) -> Decimal | None:
        return self._percentage(self.null_count)

    @property
    def completeness_percentage(self) -> Decimal | None:
        return self._percentage(self.populated_count)

    @property
    def distinct_percentage(self) -> Decimal | None:
        if self.distinct_count is None:
            return None

        return self._percentage(self.distinct_count)

    def _percentage(self, count: int) -> Decimal | None:
        if self.row_count == 0:
            return None

        return (
            Decimal(count)
            / Decimal(self.row_count)
            * Decimal("100")
        ).quantize(Decimal("0.0001"))
