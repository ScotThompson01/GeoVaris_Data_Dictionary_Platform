import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.csv_connector import CSVConnector
from app.models.data_field import DataField
from app.models.data_source import DataSource
from app.models.scan import Scan
from app.models.source_object import SourceObject


def discover_csv(
    db: Session,
    data_source_id: uuid.UUID,
    file_path: Path,
) -> Scan:
    """
    Discover technical metadata from a CSV file.

    The source file is read-only. Only normalized metadata is persisted.
    """

    data_source = db.get(DataSource, data_source_id)

    if data_source is None:
        raise ValueError("Data source not found.")

    if data_source.source_type != "csv":
        raise ValueError(
            "CSV discovery requires a CSV data source."
        )

    connector = CSVConnector()

    scan = Scan(
        data_source_id=data_source.id,
        scan_type="metadata",
        status="running",
        started_at=datetime.now(timezone.utc),
        connector_version=connector.connector_version,
    )

    db.add(scan)
    db.commit()
    db.refresh(scan)

    try:
        discovered = connector.discover(file_path)

        statement = select(SourceObject).where(
            SourceObject.data_source_id == data_source.id,
            SourceObject.object_name == discovered.object_name,
        )

        source_object = db.scalar(statement)

        if source_object is None:
            source_object = SourceObject(
                data_source_id=data_source.id,
                object_type=discovered.object_type,
                object_name=discovered.object_name,
                native_name=discovered.native_name,
                row_count=discovered.row_count,
            )

            db.add(source_object)
            db.flush()

        else:
            source_object.object_type = discovered.object_type
            source_object.native_name = discovered.native_name
            source_object.row_count = discovered.row_count

        existing_fields = {
            field.field_name: field
            for field in db.scalars(
                select(DataField).where(
                    DataField.source_object_id == source_object.id
                )
            ).all()
        }

        discovered_names = set()

        for discovered_field in discovered.fields:
            discovered_names.add(discovered_field.field_name)

            existing_field = existing_fields.get(
                discovered_field.field_name
            )

            if existing_field is None:
                existing_field = DataField(
                    source_object_id=source_object.id,
                    field_name=discovered_field.field_name,
                    ordinal_position=discovered_field.ordinal_position,
                )

                db.add(existing_field)

            existing_field.ordinal_position = (
                discovered_field.ordinal_position
            )
            existing_field.native_data_type = (
                discovered_field.native_data_type
            )
            existing_field.normalized_data_type = (
                discovered_field.normalized_data_type
            )
            existing_field.max_length = (
                discovered_field.max_length
            )
            existing_field.numeric_precision = (
                discovered_field.numeric_precision
            )
            existing_field.numeric_scale = (
                discovered_field.numeric_scale
            )
            existing_field.is_nullable = (
                discovered_field.is_nullable
            )

        scan.status = "completed"
        scan.completed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(scan)

        return scan

    except Exception as exc:
        db.rollback()

        failed_scan = db.get(Scan, scan.id)

        if failed_scan is not None:
            failed_scan.status = "failed"
            failed_scan.completed_at = datetime.now(timezone.utc)

            # Keep API/database errors useful without logging source rows.
            failed_scan.error_message = str(exc)[:2000]

            db.commit()
            db.refresh(failed_scan)

        raise