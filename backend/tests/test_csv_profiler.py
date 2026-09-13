from decimal import Decimal
from pathlib import Path

from app.profiling.csv_profiler import CSVProfiler


def test_csv_profiler_profiles_sample_file():
    profiler = CSVProfiler()

    profiles = profiler.profile(
        Path("/data/samples/customers.csv")
    )

    assert len(profiles) == 8

    by_name = {
        profile.field_name: profile
        for profile in profiles
    }

    customer_id = by_name["customer_id"]

    assert customer_id.row_count == 5
    assert customer_id.null_count == 0
    assert customer_id.null_percentage == Decimal("0.0000")
    assert customer_id.distinct_count == 5
    assert customer_id.distinct_percentage == Decimal("100.0000")
    assert customer_id.minimum_value == "1001"
    assert customer_id.maximum_value == "1005"
    assert customer_id.minimum_length == 4
    assert customer_id.maximum_length == 4

    status = by_name["status"]

    assert status.row_count == 5
    assert status.null_count == 0
    assert status.distinct_count == 3
    assert status.distinct_percentage == Decimal("60.0000")
    assert status.minimum_length == 6
    assert status.maximum_length == 8