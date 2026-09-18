from datetime import date, datetime
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.connectors.excel_connector import ExcelConnector


def _save_workbook(
    path: Path,
    worksheets: dict[str, list[list[object]]],
) -> None:
    workbook = Workbook()

    first = True

    for sheet_name, rows in worksheets.items():
        if first:
            worksheet = workbook.active
            worksheet.title = sheet_name
            first = False
        else:
            worksheet = workbook.create_sheet(
                title=sheet_name
            )

        for row in rows:
            worksheet.append(row)

    workbook.save(path)
    workbook.close()


def test_excel_connector_discovers_multiple_worksheets(
    tmp_path: Path,
):
    source = tmp_path / "customers.xlsx"

    _save_workbook(
        source,
        {
            "Customers": [
                [
                    "customer_id",
                    "name",
                    "active",
                    "balance",
                    "signup_date",
                ],
                [
                    1,
                    "Alice",
                    True,
                    10.5,
                    date(2026, 1, 1),
                ],
                [
                    2,
                    "Bob",
                    False,
                    20.25,
                    date(2026, 1, 2),
                ],
            ],
            "Orders": [
                [
                    "order_id",
                    "created_at",
                ],
                [
                    100,
                    datetime(
                        2026,
                        1,
                        3,
                        12,
                        30,
                    ),
                ],
            ],
        },
    )

    connector = ExcelConnector()

    results = connector.discover_workbook(source)

    assert len(results) == 2

    customers = results[0]

    assert customers.object_type == "worksheet"
    assert customers.object_name == "Customers"
    assert (
        customers.native_name
        == "customers.xlsx:Customers"
    )
    assert customers.row_count == 2

    field_types = {
        field.field_name: field.normalized_data_type
        for field in customers.fields
    }

    assert field_types["customer_id"] == "integer"
    assert field_types["name"] == "string"
    assert field_types["active"] == "boolean"
    assert field_types["balance"] == "decimal"
    assert field_types["signup_date"] == "date"

    assert all(
        field.is_nullable is False
        for field in customers.fields
    )

    orders = results[1]

    assert orders.object_name == "Orders"
    assert orders.row_count == 1

    assert (
        orders.fields[1].normalized_data_type
        == "datetime"
    )


def test_excel_connector_detects_nullable_fields(
    tmp_path: Path,
):
    source = tmp_path / "nullable.xlsx"

    _save_workbook(
        source,
        {
            "Customers": [
                ["customer_id", "email"],
                [1, "alice@example.com"],
                [2, None],
            ],
        },
    )

    connector = ExcelConnector()

    results = connector.discover_workbook(source)

    fields = {
        field.field_name: field
        for field in results[0].fields
    }

    assert fields["customer_id"].is_nullable is False
    assert fields["email"].is_nullable is True


def test_excel_connector_rejects_blank_column_name(
    tmp_path: Path,
):
    source = tmp_path / "blank-header.xlsx"

    _save_workbook(
        source,
        {
            "Customers": [
                ["customer_id", None],
                [1, "Alice"],
            ],
        },
    )

    connector = ExcelConnector()

    with pytest.raises(
        ValueError,
        match="blank column names",
    ):
        connector.discover_workbook(source)


def test_excel_connector_rejects_duplicate_column_names(
    tmp_path: Path,
):
    source = tmp_path / "duplicate-header.xlsx"

    _save_workbook(
        source,
        {
            "Customers": [
                ["customer_id", "customer_id"],
                [1, 2],
            ],
        },
    )

    connector = ExcelConnector()

    with pytest.raises(
        ValueError,
        match="duplicate column names",
    ):
        connector.discover_workbook(source)


def test_excel_connector_rejects_non_xlsx_file(
    tmp_path: Path,
):
    source = tmp_path / "customers.csv"
    source.write_text(
        "customer_id,name\n1,Alice\n",
        encoding="utf-8",
    )

    connector = ExcelConnector()

    with pytest.raises(
        ValueError,
        match=r"only accepts \.xlsx files",
    ):
        connector.discover_workbook(source)


def test_excel_connector_rejects_missing_file(
    tmp_path: Path,
):
    source = tmp_path / "missing.xlsx"

    connector = ExcelConnector()

    with pytest.raises(
        FileNotFoundError,
        match="Excel file does not exist",
    ):
        connector.discover_workbook(source)