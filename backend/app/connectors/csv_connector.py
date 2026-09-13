import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.connectors.base import (
    BaseConnector,
    DiscoveredField,
    DiscoveredObject,
)


class CSVConnector(BaseConnector):
    connector_name = "csv"
    connector_version = "0.2.0"

    def validate(self, source: Path) -> None:
        if not source.exists():
            raise FileNotFoundError(f"CSV file does not exist: {source}")

        if not source.is_file():
            raise ValueError("CSV source must be a file.")

        if source.suffix.lower() != ".csv":
            raise ValueError("CSV connector only accepts .csv files.")

    def discover(self, source: Path) -> DiscoveredObject:
        self.validate(source)

        with source.open(
            mode="r",
            encoding="utf-8-sig",
            newline="",
        ) as csv_file:
            reader = csv.DictReader(csv_file)

            if reader.fieldnames is None:
                raise ValueError("CSV file does not contain a header.")

            field_names = [
                field_name.strip()
                for field_name in reader.fieldnames
            ]

            if any(not field_name for field_name in field_names):
                raise ValueError(
                    "CSV file contains one or more blank column names."
                )

            if len(field_names) != len(set(field_names)):
                raise ValueError(
                    "CSV file contains duplicate column names."
                )

            values_by_field: dict[str, list[str]] = {
                field_name: []
                for field_name in field_names
            }

            row_count = 0

            for row in reader:
                row_count += 1

                for field_name in field_names:
                    raw_value = row.get(field_name)

                    if raw_value is None:
                        continue

                    value = raw_value.strip()

                    if value:
                        values_by_field[field_name].append(value)

        fields = []

        for index, field_name in enumerate(
            field_names,
            start=1,
        ):
            values = values_by_field[field_name]

            inferred_type = self._infer_type(values)

            fields.append(
                DiscoveredField(
                    field_name=field_name,
                    ordinal_position=index,
                    native_data_type=inferred_type,
                    normalized_data_type=inferred_type,
                    is_nullable=(
                        len(values) < row_count
                    ),
                )
            )

        return DiscoveredObject(
            object_type="file",
            object_name=source.name,
            native_name=source.name,
            row_count=row_count,
            fields=fields,
        )

    def _infer_type(self, values: list[str]) -> str:
        if not values:
            return "string"

        if all(self._is_boolean(value) for value in values):
            return "boolean"

        if all(self._is_integer(value) for value in values):
            return "integer"

        if all(self._is_decimal(value) for value in values):
            return "decimal"

        if all(self._is_date(value) for value in values):
            return "date"

        if all(self._is_datetime(value) for value in values):
            return "datetime"

        return "string"

    @staticmethod
    def _is_boolean(value: str) -> bool:
        return value.lower() in {
            "true",
            "false",
        }

    @staticmethod
    def _is_integer(value: str) -> bool:
        try:
            int(value)
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_decimal(value: str) -> bool:
        try:
            Decimal(value)
            return True
        except InvalidOperation:
            return False

    @staticmethod
    def _is_date(value: str) -> bool:
        try:
            datetime.strptime(
                value,
                "%Y-%m-%d",
            )
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_datetime(value: str) -> bool:
        try:
            datetime.fromisoformat(value)
            return True
        except ValueError:
            return False