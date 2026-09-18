import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.data_field import DataField
from app.models.profiling_result import ProfilingResult
from app.models.scan import Scan
from app.models.source_object import SourceObject
from app.profiling.excel_profiler import ExcelProfiler


def profile_excel_worksheet(
    db: Session,
    scan_id: uuid.UUID,
    source_object_id: uuid.UUID,
    file_path: Path,
) -> list[ProfilingResult]:
    """
    Profile one Excel worksheet and persist aggregate field-level results.

    Profiling results are associated with the supplied scan and the
    fields belonging to the supplied worksheet source object.

    Raw worksheet rows are not persisted.
    """

    scan = db.get(
        Scan,
        scan_id,
    )

    if scan is None:
        raise ValueError(
            "Scan not found."
        )

    source_object = db.get(
        SourceObject,
        source_object_id,
    )

    if source_object is None:
        raise ValueError(
            "Source object not found."
        )

    if source_object.object_type != "worksheet":
        raise ValueError(
            "Excel profiling requires a worksheet source object."
        )

    fields = db.scalars(
        select(DataField)
        .where(
            DataField.source_object_id
            == source_object_id
        )
        .order_by(
            DataField.ordinal_position
        )
    ).all()

    if not fields:
        raise ValueError(
            "No data fields found for the source object."
        )

    field_types = {
        field.field_name: field.normalized_data_type
        for field in fields
    }

    profiler = ExcelProfiler()

    profiles = profiler.profile(
        file_path,
        worksheet_name=source_object.object_name,
        field_types=field_types,
    )

    fields_by_name = {
        field.field_name: field
        for field in fields
    }

    field_ids = [
        field.id
        for field in fields
    ]

    # Replace results only for fields belonging to this worksheet.
    # Other worksheets in the same scan must remain intact.
    db.execute(
        delete(ProfilingResult).where(
            ProfilingResult.scan_id == scan_id,
            ProfilingResult.data_field_id.in_(
                field_ids
            ),
        )
    )

    persisted: list[ProfilingResult] = []

    for profile in profiles:
        data_field = fields_by_name.get(
            profile.field_name
        )

        if data_field is None:
            continue

        result = ProfilingResult(
            scan_id=scan.id,
            data_field_id=data_field.id,
            row_count=profile.row_count,
            null_count=profile.null_count,
            null_percentage=profile.null_percentage,
            distinct_count=profile.distinct_count,
            distinct_percentage=profile.distinct_percentage,
            minimum_value=profile.minimum_value,
            maximum_value=profile.maximum_value,
            minimum_length=profile.minimum_length,
            maximum_length=profile.maximum_length,
        )

        db.add(result)
        persisted.append(result)

    db.commit()

    for result in persisted:
        db.refresh(result)

    return persisted