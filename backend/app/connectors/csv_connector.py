import csv
from pathlib import Path

from app.connectors.base import (
    BaseConnector,
    DiscoveredField,
    DiscoveredObject,
)


class CSVConnector(BaseConnector):
    connector_name = "csv"
    connector_version = "0.1.0"

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
            reader = csv.reader(csv_file)

            try:
                header = next(reader)
            except StopIteration as exc:
                raise ValueError("CSV file is empty.") from exc

            cleaned_header = [
                column_name.strip()
                for column_name in header
            ]

            if not cleaned_header:
                raise ValueError("CSV file does not contain a header.")

            if any(not column_name for column_name in cleaned_header):
                raise ValueError(
                    "CSV file contains one or more blank column names."
                )

            if len(cleaned_header) != len(set(cleaned_header)):
                raise ValueError(
                    "CSV file contains duplicate column names."
                )

            row_count = sum(1 for _ in reader)

        fields = [
            DiscoveredField(
                field_name=column_name,
                ordinal_position=index,
            )
            for index, column_name in enumerate(
                cleaned_header,
                start=1,
            )
        ]

        return DiscoveredObject(
            object_type="file",
            object_name=source.name,
            native_name=source.name,
            row_count=row_count,
            fields=fields,
        )