import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.connectors.database.base import DatabaseConnectionConfig
from app.connectors.database.postgresql_connector import (
    PostgreSQLConnector,
)
from app.models.data_source import DataSource
from app.models.scan import Scan
from app.services.discovery_persistence import (
    persist_discovered_object,
)


def discover_postgresql(
    db: Session,
    data_source_id: uuid.UUID,
    connection_config: DatabaseConnectionConfig,
    password: str | None = None,
) -> Scan:
    """
    Discover PostgreSQL technical metadata and persist it in GeoVaris.

    Connection credentials are supplied at runtime and are not
    persisted by this service.

    PostgreSQL discovery is metadata-only and uses the connector's
    read-only database session.
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

    if data_source.source_type != "postgresql":
        raise ValueError(
            "PostgreSQL discovery requires a PostgreSQL data source."
        )

    if not data_source.is_active:
        raise ValueError(
            "PostgreSQL data source is inactive."
        )

    connector = PostgreSQLConnector()

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
        # 3. Validate the read-only PostgreSQL connection
        # -----------------------------------------------------

        connector.validate_connection(
            config=connection_config,
            password=password,
        )

        # -----------------------------------------------------
        # 4. Discover normalized PostgreSQL metadata
        # -----------------------------------------------------

        discovered_objects = connector.discover_objects(
            config=connection_config,
            password=password,
        )

        # -----------------------------------------------------
        # 5. Persist every discovered object and its fields
        # -----------------------------------------------------

        for discovered_object in discovered_objects:
            persist_discovered_object(
                db=db,
                data_source=data_source,
                discovered=discovered_object,
            )

        # -----------------------------------------------------
        # 6. Mark the scan completed
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
        # Roll back any uncommitted discovery changes.
        db.rollback()

        # The initial scan record was committed before discovery,
        # so it can be reloaded and marked as failed.
        failed_scan = db.get(
            Scan,
            scan.id,
        )

        if failed_scan is not None:
            failed_scan.status = "failed"

            failed_scan.completed_at = datetime.now(
                timezone.utc
            )

            # Save a generic error; driver exceptions may contain
            # connection details or credentials.
            failed_scan.error_message = "PostgreSQL metadata discovery failed."

            db.commit()
            db.refresh(failed_scan)

        raise