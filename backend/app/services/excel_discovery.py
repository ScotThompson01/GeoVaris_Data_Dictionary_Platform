import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.connectors.excel_connector import ExcelConnector
from app.models.data_source import DataSource
from app.models.scan import Scan
from app.services.discovery_persistence import (
    persist_discovered_object,
)


def discover_excel(
    db: Session,
    data_source_id: uuid.UUID,
    file_path: Path,
) -> Scan:
    """
    Discover technical metadata from an Excel workbook.

    The source workbook is opened read-only.

    Each worksheet is persisted as a separate source object.

    Raw workbook rows are not persisted by this service.
    Human-maintained governance metadata is not modified.
    """

    # ---------------------------------------------------------
    # 1. Validate the GeoVaris data source
    # ---------------------------------------------------------

    data_source = db.get(
        DataSource,
        data_source_id,
    )

    if data_source is None:
        raise ValueError(
            "Data source not found."
        )

    if data_source.source_type != "excel":
        raise ValueError(
            "Excel discovery requires an Excel data source."
        )

    if not data_source.is_active:
        raise ValueError(
            "Excel discovery requires an active data source."
        )

    connector = ExcelConnector()

    # ---------------------------------------------------------
    # 2. Create the scan record
    # ---------------------------------------------------------

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
        # -----------------------------------------------------
        # 3. Discover each worksheet in the workbook
        # -----------------------------------------------------

        discovered_objects = (
            connector.discover_workbook(
                file_path
            )
        )

        # -----------------------------------------------------
        # 4. Persist each worksheet independently
        # -----------------------------------------------------

        for discovered in discovered_objects:
            persist_discovered_object(
                db=db,
                data_source=data_source,
                discovered=discovered,
            )

        # -----------------------------------------------------
        # 5. Mark the scan completed
        # -----------------------------------------------------

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
        # Roll back any uncommitted worksheet or field changes.
        db.rollback()

        # The scan was committed before discovery began,
        # so reload it and record the failed execution.
        failed_scan = db.get(
            Scan,
            scan.id,
        )

        if failed_scan is not None:
            failed_scan.status = "failed"
            failed_scan.completed_at = datetime.now(
                timezone.utc
            )

            # Keep diagnostics bounded. Raw workbook rows are
            # never intentionally stored in this message.
            failed_scan.error_message = str(exc)[:2000]

            db.commit()
            db.refresh(failed_scan)

        raise