"""Metadata-only authorization for basic PostgreSQL profiling requests.

This service does not authorize a source connection or execute profiling.
Connection verification and orchestration require separate security gates.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.data_field import DataField
from app.models.data_source import DataSource
from app.models.scan import Scan
from app.models.source_object import SourceObject
from app.services.data_source_authorization import require_data_source_access
from app.services.postgresql_profiling_execution_policy import (
    require_postgresql_profiling_execution_enabled,
)


@dataclass(frozen=True)
class PostgreSQLBasicProfilingRequest:
    """Validated metadata relationships, not source execution permission."""

    source: DataSource
    scan: Scan
    field: DataField
    source_object: SourceObject


def authorize_postgresql_basic_profiling_request(
    *,
    db: Session,
    user_id: uuid.UUID,
    data_source_id: uuid.UUID,
    scan_id: uuid.UUID,
    data_field_id: uuid.UUID,
) -> PostgreSQLBasicProfilingRequest:
    """Validate deployment, project access, and profiling metadata."""

    require_postgresql_profiling_execution_enabled(settings)

    source = require_data_source_access(
        db,
        user_id=user_id,
        data_source_id=data_source_id,
    )

    if source.id != data_source_id:
        raise ValueError("Authorized source identity does not match request.")

    if source.source_type != "postgresql":
        raise ValueError("PostgreSQL profiling requires a PostgreSQL source.")

    if source.is_active is not True:
        raise ValueError("PostgreSQL profiling source is inactive.")

    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ValueError("Profiling scan not found.")

    if scan.data_source_id != source.id:
        raise ValueError("Profiling scan does not belong to the source.")

    if scan.scan_type != "basic_profile":
        raise ValueError("Only basic PostgreSQL profiling is authorized.")

    if scan.status != "running":
        raise ValueError("Profiling scan must be running.")

    field = db.get(DataField, data_field_id)
    if field is None:
        raise ValueError("Data field not found.")

    source_object = db.get(SourceObject, field.source_object_id)
    if source_object is None:
        raise ValueError("Source object not found.")

    if source_object.data_source_id != source.id:
        raise ValueError("Data field does not belong to the profiling source.")

    return PostgreSQLBasicProfilingRequest(
        source=source,
        scan=scan,
        field=field,
        source_object=source_object,
    )
