import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass(frozen=True)
class FieldProfile:
    field_name: str
    row_count: int
    null_count: int
    null_percentage: Decimal
    distinct_count: int
    distinct_percentage: Decimal
    minimum_value: str | None
    maximum_value: str | None
    minimum_length: int | None
    maximum_length: int | None


class CSVProfiler:
    def profile(
        self,
        source: Path,
        field_types: dict[str, str | None] | None = None,
    ) -> list[FieldProfile]:
        """
        Profile a CSV file and return aggregate field-level statistics.

        Raw source rows are read in memory only for profiling and are not
        persisted by this class.
        """

        self._validate(source)

        field_types = field_types or {}

        with source.open(
            mode="r",
            encoding="utf-8-sig",
            newline="",
        ) as csv_file:
            reader = csv.DictReader(csv_file)

            if reader.fieldnames is None:
                raise ValueError(
                    "CSV file does not contain a header."
                )

            field_names = [
                field_name.strip()
                for field_name in reader.fieldnames
            ]

            self._validate_headers(field_names)

            values_by_field: dict[str, list[str | None]] = {
                field_name: []
                for field_name in field_names
            }

            row_count = 0

            for row in reader:
                row_count += 1

                for field_name in field_names:
                    raw_value = row.get(field_name)

                    if raw_value is None:
                        values_by_field[field_name].append(None)
                        continue

                    value = raw_value.strip()

                    values_by_field[field_name].append(
                        value if value != "" else None
                    )

        profiles: list[FieldProfile] = []

        for field_name in field_names:
            values = values_by_field[field_name]

            populated_values = [
                value
                for value in values
                if value is not None
            ]

            null_count = row_count - len(populated_values)

            null_percentage = self._percentage(
                numerator=null_count,
                denominator=row_count,
            )

            distinct_count = len(set(populated_values))

            distinct_percentage = self._percentage(
                numerator=distinct_count,
                denominator=row_count,
            )

            minimum_value, maximum_value = self._typed_min_max(
                values=populated_values,
                normalized_data_type=field_types.get(field_name),
            )

            lengths = [
                len(value)
                for value in populated_values
            ]

            minimum_length = min(lengths) if lengths else None
            maximum_length = max(lengths) if lengths else None

            profiles.append(
                FieldProfile(
                    field_name=field_name,
                    row_count=row_count,
                    null_count=null_count,
                    null_percentage=null_percentage,
                    distinct_count=distinct_count,
                    distinct_percentage=distinct_percentage,
                    minimum_value=minimum_value,
                    maximum_value=maximum_value,
                    minimum_length=minimum_length,
                    maximum_length=maximum_length,
                )
            )

        return profiles

    @staticmethod
    def _validate(source: Path) -> None:
        if not source.exists():
            raise FileNotFoundError(
                f"CSV file does not exist: {source}"
            )

        if not source.is_file():
            raise ValueError(
                "CSV source must be a file."
            )

        if source.suffix.lower() != ".csv":
            raise ValueError(
                "CSV profiler only accepts .csv files."
            )

    @staticmethod
    def _validate_headers(
        field_names: list[str],
    ) -> None:
        if not field_names:
            raise ValueError(
                "CSV file does not contain a header."
            )

        if any(not field_name for field_name in field_names):
            raise ValueError(
                "CSV file contains one or more blank column names."
            )

        if len(field_names) != len(set(field_names)):
            raise ValueError(
                "CSV file contains duplicate column names."
            )

    @staticmethod
    def _percentage(
        numerator: int,
        denominator: int,
    ) -> Decimal:
        if denominator == 0:
            return Decimal("0.0000")

        percentage = (
            Decimal(numerator)
            / Decimal(denominator)
            * Decimal("100")
        )

        return percentage.quantize(
            Decimal("0.0001")
        )

    @staticmethod
    def _typed_min_max(
        values: list[str],
        normalized_data_type: str | None,
    ) -> tuple[str | None, str | None]:
        if not values:
            return None, None

        try:
            if normalized_data_type == "integer":
                typed_values = [
                    int(value)
                    for value in values
                ]

                return (
                    str(min(typed_values)),
                    str(max(typed_values)),
                )

            if normalized_data_type == "decimal":
                typed_values = [
                    Decimal(value)
                    for value in values
                ]

                return (
                    str(min(typed_values)),
                    str(max(typed_values)),
                )

            if normalized_data_type == "date":
                typed_values = [
                    datetime.strptime(
                        value,
                        "%Y-%m-%d",
                    ).date()
                    for value in values
                ]

                return (
                    min(typed_values).isoformat(),
                    max(typed_values).isoformat(),
                )

            if normalized_data_type == "datetime":
                typed_values = [
                    datetime.fromisoformat(value)
                    for value in values
                ]

                return (
                    min(typed_values).isoformat(),
                    max(typed_values).isoformat(),
                )

        except (ValueError, InvalidOperation):
            # Fall back to lexical comparison if values cannot be
            # converted cleanly to their expected technical type.
            pass

        return (
            min(values),
            max(values),
        )