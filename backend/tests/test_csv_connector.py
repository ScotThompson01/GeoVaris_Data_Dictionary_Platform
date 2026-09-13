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