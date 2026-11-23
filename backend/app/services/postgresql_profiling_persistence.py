"""Persist normalized PostgreSQL aggregate profiling measurements.

This service does not execute source queries or commit transactions.
Authorization must be established by the calling workflow.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.data_field import DataField
from app.models.data_source import DataSource
from app.models.profiling_result import ProfilingResult
from app.models.scan import Scan
from app.models.source_object import SourceObject
from app.profiling.database_profile import DatabaseFieldProfile


def persist_postgresql_field_profile(
    *,
    db: Session,
    scan_id: uuid.UUID,
    data_field_id: uuid.UUID,
    profile: DatabaseFieldProfile,
) -> ProfilingResult:
    """Stage one aggregate measurement in the caller's transaction."""

    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ValueError("Profiling scan not found.")

    if scan.scan_type not in {
        "basic_profile",
        "approved_sample",
        "full_profile",
    }:
        raise ValueError("Scan is not a profiling scan.")

    if scan.status != "running":
        raise ValueError("Profiling scan must be running.")

    source = db.get(DataSource, scan.data_source_id)
    if source is None:
        raise ValueError("Data source not found.")

    if source.source_type != "postgresql":
        raise ValueError("PostgreSQL profiling requires a PostgreSQL source.")

    field = db.get(DataField, data_field_id)
    if field is None:
        raise ValueError("Data field not found.")

    source_object = db.get(SourceObject, field.source_object_id)
    if source_object is None:
        raise ValueError("Source object not found.")

    if source_object.data_source_id != source.id:
        raise ValueError("Field does not belong to the profiling source.")

    if (
        source_object.schema_name != profile.schema_name
        or source_object.object_name != profile.object_name
        or field.field_name != profile.field_name
    ):
        raise ValueError("Profile identity does not match the data field.")

    existing = db.scalar(
        select(ProfilingResult).where(
            ProfilingResult.scan_id == scan_id,
            ProfilingResult.data_field_id == data_field_id,
        )
    )

    if existing is not None:
        raise ValueError(
            "Profiling result already exists for this scan and field."
        )

    result = ProfilingResult(
        scan_id=scan_id,
        data_field_id=data_field_id,
    )
    db.add(result)

    result.row_count = profile.row_count
    result.null_count = profile.null_count
    result.null_percentage = profile.null_percentage
    result.distinct_count = profile.distinct_count
    result.distinct_percentage = profile.distinct_percentage
    result.minimum_value = profile.minimum_value
    result.maximum_value = profile.maximum_value
    result.minimum_length = profile.minimum_length
    result.maximum_length = profile.maximum_length

    db.flush()
    return result
