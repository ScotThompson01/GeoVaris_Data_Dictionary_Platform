from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.connectors.database.base import DatabaseConnectionConfig
from app.connectors.database.sqlserver_connector import SQLServerConnector
from app.models.data_source import DataSource
from app.models.scan import Scan
from app.services.discovery_persistence import persist_discovered_object


def discover_sqlserver(
    db: Session,
    data_source_id: UUID,
    connection_config: DatabaseConnectionConfig,
    password: str,
) -> Scan:
    data_source = db.get(DataSource, data_source_id)

    if data_source is None:
        raise ValueError("Data source not found.")

    if data_source.source_type != "sqlserver":
        raise ValueError(
            "Data source is not configured as a SQL Server source."
        )

    if not data_source.is_active:
        raise ValueError("Data source is inactive.")

    connector = SQLServerConnector()

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
        connector.validate_connection(
            config=connection_config,
            password=password,
        )

        discovered_objects = connector.discover_objects(
            config=connection_config,
            password=password,
        )

        for discovered in discovered_objects:
            persist_discovered_object(
                db=db,
                data_source=data_source,
                discovered=discovered,
            )

        scan = db.get(Scan, scan.id)
        scan.status = "completed"
        scan.completed_at = datetime.now(timezone.utc)
        scan.error_message = None

        db.commit()
        db.refresh(scan)

        return scan

    except Exception as exc:
        db.rollback()

        scan = db.get(Scan, scan.id)

        if scan is not None:
            scan.status = "failed"
            scan.completed_at = datetime.now(timezone.utc)
            scan.error_message = str(exc)[:2000]

            db.commit()
            db.refresh(scan)

        raise