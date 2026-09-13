from pathlib import Path

from app.connectors.csv_connector import CSVConnector


def test_csv_connector_discovers_sample_file():
    connector = CSVConnector()

    result = connector.discover(
        Path("/data/samples/customers.csv")
    )

    assert result.object_name == "customers.csv"
    assert result.object_type == "file"
    assert result.row_count == 5
    assert len(result.fields) == 8

    assert result.fields[0].field_name == "customer_id"
    assert result.fields[0].ordinal_position == 1

    assert result.fields[-1].field_name == "longitude"
    assert result.fields[-1].ordinal_position == 8

    field_types = {
        field.field_name: field.normalized_data_type
        for field in result.fields
    }

    assert field_types["customer_id"] == "integer"
    assert field_types["first_name"] == "string"
    assert field_types["last_name"] == "string"
    assert field_types["email"] == "string"
    assert field_types["status"] == "string"
    assert field_types["signup_date"] == "date"
    assert field_types["latitude"] == "decimal"
    assert field_types["longitude"] == "decimal"

    assert all(
        field.is_nullable is False
        for field in result.fields
    )