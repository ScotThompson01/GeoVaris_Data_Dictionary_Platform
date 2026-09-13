from pathlib import Path

from app.profiling.csv_profiler import CSVProfiler


def test_csv_discovery_and_profiling_agree_on_sample_file():
    """
    Integration boundary test for the CSV metadata/profiling pipeline.

    Confirms that the sample CSV can be discovered and profiled
    consistently without modifying the source file.
    """
    from app.connectors.csv_connector import CSVConnector

    source = Path("/data/samples/customers.csv")

    connector = CSVConnector()
    discovered = connector.discover(source)

    field_types = {
        field.field_name: field.normalized_data_type
        for field in discovered.fields
    }

    profiler = CSVProfiler()

    profiles = profiler.profile(
        source,
        field_types=field_types,
    )

    assert discovered.object_name == "customers.csv"
    assert discovered.row_count == 5
    assert len(discovered.fields) == 8
    assert len(profiles) == 8

    discovered_names = {
        field.field_name
        for field in discovered.fields
    }

    profiled_names = {
        profile.field_name
        for profile in profiles
    }

    assert discovered_names == profiled_names

    profiles_by_name = {
        profile.field_name: profile
        for profile in profiles
    }

    customer_id = profiles_by_name["customer_id"]

    assert customer_id.row_count == 5
    assert customer_id.null_count == 0
    assert customer_id.distinct_count == 5
    assert customer_id.minimum_value == "1001"
    assert customer_id.maximum_value == "1005"

    status = profiles_by_name["status"]

    assert status.row_count == 5
    assert status.null_count == 0
    assert status.distinct_count == 3