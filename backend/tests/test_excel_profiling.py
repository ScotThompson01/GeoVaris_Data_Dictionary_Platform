import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.models.data_field import DataField
from app.models.profiling_result import ProfilingResult
from app.models.scan import Scan
from app.models.source_object import SourceObject
from app.profiling.excel_profiler import FieldProfile
from app.services.excel_profiling import profile_excel_worksheet


def _make_scan() -> Scan:
    return Scan(
        id=uuid.uuid4(),
        data_source_id=uuid.uuid4(),
        scan_type="metadata",
        status="running",
    )


def _make_source_object() -> SourceObject:
    return SourceObject(
        id=uuid.uuid4(),
        data_source_id=uuid.uuid4(),
        object_type="worksheet",
        object_name="Customers",
    )


def _make_field(
    source_object_id: uuid.UUID,
    name: str,
    position: int,
    normalized_type: str,
) -> DataField:
    return DataField(
        id=uuid.uuid4(),
        source_object_id=source_object_id,
        field_name=name,
        ordinal_position=position,
        normalized_data_type=normalized_type,
    )


def test_profile_excel_worksheet_persists_results():
    db = MagicMock()

    scan = _make_scan()
    source_object = _make_source_object()

    customer_id = _make_field(
        source_object.id,
        "customer_id",
        1,
        "integer",
    )

    status = _make_field(
        source_object.id,
        "status",
        2,
        "string",
    )

    db.get.side_effect = [
        scan,
        source_object,
    ]

    db.scalars.return_value.all.return_value = [
        customer_id,
        status,
    ]

    profiles = [
        FieldProfile(
            field_name="customer_id",
            row_count=3,
            null_count=0,
            null_percentage=Decimal("0.0000"),
            distinct_count=3,
            distinct_percentage=Decimal("100.0000"),
            minimum_value="1001",
            maximum_value="1003",
            minimum_length=4,
            maximum_length=4,
        ),
        FieldProfile(
            field_name="status",
            row_count=3,
            null_count=0,
            null_percentage=Decimal("0.0000"),
            distinct_count=2,
            distinct_percentage=Decimal("66.6667"),
            minimum_value="ACTIVE",
            maximum_value="INACTIVE",
            minimum_length=6,
            maximum_length=8,
        ),
    ]

    with patch(
        "app.services.excel_profiling.ExcelProfiler"
    ) as profiler_class:
        profiler = profiler_class.return_value
        profiler.profile.return_value = profiles

        results = profile_excel_worksheet(
            db=db,
            scan_id=scan.id,
            source_object_id=source_object.id,
            file_path=Path("/data/samples/customers.xlsx"),
        )

    profiler.profile.assert_called_once_with(
        Path("/data/samples/customers.xlsx"),
        worksheet_name="Customers",
        field_types={
            "customer_id": "integer",
            "status": "string",
        },
    )

    assert len(results) == 2

    assert all(
        isinstance(result, ProfilingResult)
        for result in results
    )

    assert results[0].scan_id == scan.id
    assert results[0].data_field_id == customer_id.id
    assert results[0].row_count == 3
    assert results[0].distinct_count == 3

    assert results[1].data_field_id == status.id
    assert results[1].distinct_count == 2

    db.execute.assert_called_once()
    assert db.add.call_count == 2
    db.commit.assert_called_once()
    assert db.refresh.call_count == 2


def test_profile_excel_worksheet_rejects_missing_scan():
    db = MagicMock()
    db.get.return_value = None

    try:
        profile_excel_worksheet(
            db=db,
            scan_id=uuid.uuid4(),
            source_object_id=uuid.uuid4(),
            file_path=Path("/data/samples/customers.xlsx"),
        )
    except ValueError as exc:
        assert str(exc) == "Scan not found."
    else:
        raise AssertionError(
            "Expected ValueError."
        )

    db.execute.assert_not_called()
    db.commit.assert_not_called()


def test_profile_excel_worksheet_rejects_missing_source_object():
    db = MagicMock()

    scan = _make_scan()

    db.get.side_effect = [
        scan,
        None,
    ]

    try:
        profile_excel_worksheet(
            db=db,
            scan_id=scan.id,
            source_object_id=uuid.uuid4(),
            file_path=Path("/data/samples/customers.xlsx"),
        )
    except ValueError as exc:
        assert str(exc) == "Source object not found."
    else:
        raise AssertionError(
            "Expected ValueError."
        )

    db.execute.assert_not_called()
    db.commit.assert_not_called()


def test_profile_excel_worksheet_rejects_non_worksheet_object():
    db = MagicMock()

    scan = _make_scan()

    source_object = SourceObject(
        id=uuid.uuid4(),
        data_source_id=uuid.uuid4(),
        object_type="table",
        object_name="customers",
    )

    db.get.side_effect = [
        scan,
        source_object,
    ]

    try:
        profile_excel_worksheet(
            db=db,
            scan_id=scan.id,
            source_object_id=source_object.id,
            file_path=Path("/data/samples/customers.xlsx"),
        )
    except ValueError as exc:
        assert str(exc) == (
            "Excel profiling requires a worksheet source object."
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )

    db.execute.assert_not_called()
    db.commit.assert_not_called()


def test_profile_excel_worksheet_rejects_missing_fields():
    db = MagicMock()

    scan = _make_scan()
    source_object = _make_source_object()

    db.get.side_effect = [
        scan,
        source_object,
    ]

    db.scalars.return_value.all.return_value = []

    try:
        profile_excel_worksheet(
            db=db,
            scan_id=scan.id,
            source_object_id=source_object.id,
            file_path=Path("/data/samples/customers.xlsx"),
        )
    except ValueError as exc:
        assert str(exc) == (
            "No data fields found for the source object."
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )

    db.execute.assert_not_called()
    db.commit.assert_not_called()