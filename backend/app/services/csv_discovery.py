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
from app.services.csv_profiling import profile_csv


def discover_csv(
    db: Session,
    data_source_id: uuid.UUID,
    file_path: Path,
) -> Scan:
    """
    Discover technical metadata from a CSV file and run basic profiling.

    The source CSV is read-only.

    Persisted information includes:
    - Scan execution metadata
    - Source Object metadata
    - Data Field metadata
    - Aggregate Profiling Results

    Raw CSV rows are not persisted.
    """

    data_source = db.get(
        DataSource,
        data_source_id,
    )

    if data_source is None:
        raise ValueError(
            "Data source not found."
        )

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
        # ---------------------------------------------------------
        # 1. Discover normalized metadata from the CSV
        # ---------------------------------------------------------

        discovered = connector.discover(
            file_path
        )

        # ---------------------------------------------------------
        # 2. Find or create the Source Object
        # ---------------------------------------------------------

        source_object = db.scalar(
            select(SourceObject).where(
                SourceObject.data_source_id == data_source.id,
                SourceObject.object_name == discovered.object_name,
            )
        )

        if source_object is None:
            source_object = SourceObject(
                data_source_id=data_source.id,
                object_type=discovered.object_type,
                object_name=discovered.object_name,
                native_name=discovered.native_name,
                row_count=discovered.row_count,
            )

            db.add(source_object)

            # Generate the SourceObject ID without committing yet.
            db.flush()

        else:
            source_object.object_type = discovered.object_type
            source_object.native_name = discovered.native_name
            source_object.row_count = discovered.row_count

        # ---------------------------------------------------------
        # 3. Load existing Data Fields
        # ---------------------------------------------------------

        existing_fields = {
            field.field_name: field
            for field in db.scalars(
                select(DataField).where(
                    DataField.source_object_id == source_object.id
                )
            ).all()
        }

        # ---------------------------------------------------------
        # 4. Create or update discovered Data Fields
        # ---------------------------------------------------------

        for discovered_field in discovered.fields:
            data_field = existing_fields.get(
                discovered_field.field_name
            )

            if data_field is None:
                data_field = DataField(
                    source_object_id=source_object.id,
                    field_name=discovered_field.field_name,
                    ordinal_position=discovered_field.ordinal_position,
                )

                db.add(data_field)

            data_field.ordinal_position = (
                discovered_field.ordinal_position
            )

            data_field.native_data_type = (
                discovered_field.native_data_type
            )

            data_field.normalized_data_type = (
                discovered_field.normalized_data_type
            )

            data_field.max_length = (
                discovered_field.max_length
            )

            data_field.numeric_precision = (
                discovered_field.numeric_precision
            )

            data_field.numeric_scale = (
                discovered_field.numeric_scale
            )

            data_field.is_nullable = (
                discovered_field.is_nullable
            )

            data_field.is_primary_key = (
                discovered_field.is_primary_key
            )

            data_field.is_unique = (
                discovered_field.is_unique
            )

            data_field.source_comment = (
                discovered_field.source_comment
            )

        # Ensure all new/updated fields are available to the
        # profiling service before profiling begins.
        db.flush()

        # ---------------------------------------------------------
        # 5. Run basic CSV profiling
        # ---------------------------------------------------------

        profile_csv(
            db=db,
            scan_id=scan.id,
            source_object_id=source_object.id,
            file_path=file_path,
        )

        # ---------------------------------------------------------
        # 6. Mark the Scan completed
        # ---------------------------------------------------------

        scan = db.get(
            Scan,
            scan.id,
        )

        if scan is None:
            raise RuntimeError(
                "Scan record could not be reloaded."
            )

        scan.status = "completed"
        scan.completed_at = datetime.now(
            timezone.utc
        )
        scan.error_message = None

        db.commit()
        db.refresh(scan)

        return scan

    except Exception as exc:
        # Roll back any uncommitted metadata changes.
        db.rollback()

        failed_scan = db.get(
            Scan,
            scan.id,
        )

        if failed_scan is not None:
            failed_scan.status = "failed"

            failed_scan.completed_at = datetime.now(
                timezone.utc
            )

            # Store a bounded diagnostic message.
            # Raw source rows are never intentionally logged here.
            failed_scan.error_message = str(exc)[:2000]

            db.commit()
            db.refresh(failed_scan)

        raise