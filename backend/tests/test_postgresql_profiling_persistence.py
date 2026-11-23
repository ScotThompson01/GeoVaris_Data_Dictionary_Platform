"""Offline tests for PostgreSQL profiling result persistence."""

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models.profiling_result import ProfilingResult
from app.profiling.database_profile import DatabaseFieldProfile
from app.services.postgresql_profiling_persistence import (
    complete_postgresql_profiling_scan,
    persist_postgresql_field_profile,
)


SCAN_ID = uuid.UUID("00000000-0000-0000-0000-000000000101")
SOURCE_ID = uuid.UUID("00000000-0000-0000-0000-000000000102")
OBJECT_ID = uuid.UUID("00000000-0000-0000-0000-000000000103")
FIELD_ID = uuid.UUID("00000000-0000-0000-0000-000000000104")


def make_profile() -> DatabaseFieldProfile:
    return DatabaseFieldProfile(
        schema_name="public",
        object_name="synthetic_customers",
        field_name="customer_id",
        row_count=100,
        null_count=5,
        distinct_count=None,
    )


def make_session(
    *,
    scan_type: str = "basic_profile",
    scan_status: str = "running",
    source_type: str = "postgresql",
    object_source_id: uuid.UUID = SOURCE_ID,
    schema_name: str = "public",
    field_name: str = "customer_id",
    existing: ProfilingResult | None = None,
) -> MagicMock:
    db = MagicMock()

    scan = SimpleNamespace(
        id=SCAN_ID,
        data_source_id=SOURCE_ID,
        scan_type=scan_type,
        status=scan_status,
    )
    source = SimpleNamespace(
        id=SOURCE_ID,
        source_type=source_type,
    )
    field = SimpleNamespace(
        id=FIELD_ID,
        source_object_id=OBJECT_ID,
        field_name=field_name,
    )
    source_object = SimpleNamespace(
        id=OBJECT_ID,
        data_source_id=object_source_id,
        schema_name=schema_name,
        object_name="synthetic_customers",
    )

    from app.models.scan import Scan
    from app.models.data_source import DataSource
    from app.models.data_field import DataField
    from app.models.source_object import SourceObject

    values = {
        (Scan, SCAN_ID): scan,
        (DataSource, SOURCE_ID): source,
        (DataField, FIELD_ID): field,
        (SourceObject, OBJECT_ID): source_object,
    }

    db.get.side_effect = lambda model, identity: values.get(
        (model, identity)
    )
    db.scalar.return_value = existing

    return db


def persist(db: MagicMock) -> ProfilingResult:
    return persist_postgresql_field_profile(
        db=db,
        scan_id=SCAN_ID,
        data_field_id=FIELD_ID,
        profile=make_profile(),
    )


def test_new_measurement_is_staged_without_commit() -> None:
    db = make_session()

    result = persist(db)

    assert isinstance(result, ProfilingResult)
    assert result.scan_id == SCAN_ID
    assert result.data_field_id == FIELD_ID
    assert result.row_count == 100
    assert result.null_count == 5
    assert result.null_percentage == Decimal("5.0000")
    assert result.distinct_count is None
    assert result.distinct_percentage is None

    db.add.assert_called_once_with(result)
    db.flush.assert_called_once()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_existing_measurement_is_preserved_and_duplicate_rejected() -> None:
    existing = ProfilingResult(
        scan_id=SCAN_ID,
        data_field_id=FIELD_ID,
        row_count=50,
        null_count=0,
        distinct_count=40,
        null_percentage=Decimal("0"),
        distinct_percentage=Decimal("80"),
    )
    db = make_session(existing=existing)

    with pytest.raises(ValueError, match="already exists"):
        persist(db)

    assert existing.row_count == 50
    assert existing.null_count == 0
    assert existing.distinct_count == 40
    assert existing.distinct_percentage == Decimal("80")

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"scan_type": "metadata"}, "not a profiling scan"),
        ({"scan_status": "completed"}, "must be running"),
        ({"source_type": "csv"}, "requires a PostgreSQL source"),
        (
            {"object_source_id": uuid.UUID(
                "00000000-0000-0000-0000-000000000999"
            )},
            "does not belong",
        ),
        ({"schema_name": "other"}, "identity does not match"),
        ({"field_name": "other"}, "identity does not match"),
    ],
)
def test_invalid_relationships_are_rejected(
    override: dict,
    message: str,
) -> None:
    db = make_session(**override)

    with pytest.raises(ValueError, match=message):
        persist(db)

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_missing_scan_is_rejected() -> None:
    db = make_session()
    db.get.side_effect = lambda model, identity: None

    with pytest.raises(ValueError, match="Profiling scan not found"):
        persist(db)

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()

def make_completion_session(
    *,
    scan_type: str = "basic_profile",
    scan_status: str = "running",
    source_type: str = "postgresql",
    result_exists: bool = True,
) -> tuple[MagicMock, SimpleNamespace]:
    from app.models.scan import Scan
    from app.models.data_source import DataSource

    db = MagicMock()

    scan = SimpleNamespace(
        id=SCAN_ID,
        data_source_id=SOURCE_ID,
        scan_type=scan_type,
        status=scan_status,
        completed_at=None,
        error_message="previous status",
    )

    source = SimpleNamespace(
        id=SOURCE_ID,
        source_type=source_type,
    )

    values = {
        (Scan, SCAN_ID): scan,
        (DataSource, SOURCE_ID): source,
    }

    db.get.side_effect = lambda model, identity: values.get(
        (model, identity)
    )

    db.scalar.return_value = (
        uuid.uuid4() if result_exists else None
    )

    return db, scan


def test_profiling_scan_completion_stages_success_without_commit() -> None:
    from datetime import datetime, timezone

    db, scan = make_completion_session()

    result = complete_postgresql_profiling_scan(
        db=db,
        scan_id=SCAN_ID,
    )

    assert result is scan
    assert scan.status == "completed"
    assert isinstance(scan.completed_at, datetime)
    assert scan.completed_at.tzinfo is not None
    assert scan.completed_at.utcoffset().total_seconds() == 0
    assert scan.error_message is None

    db.flush.assert_called_once()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_profiling_scan_completion_rejects_empty_scan() -> None:
    db, scan = make_completion_session(result_exists=False)

    with pytest.raises(ValueError, match="without measurements"):
        complete_postgresql_profiling_scan(
            db=db,
            scan_id=SCAN_ID,
        )

    assert scan.status == "running"
    assert scan.completed_at is None
    db.flush.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"scan_type": "metadata"}, "not a profiling scan"),
        ({"scan_status": "completed"}, "must be running"),
        ({"scan_status": "failed"}, "must be running"),
        ({"source_type": "csv"}, "source not found"),
    ],
)
def test_profiling_scan_completion_rejects_invalid_state(
    override: dict,
    message: str,
) -> None:
    db, scan = make_completion_session(**override)

    with pytest.raises(ValueError, match=message):
        complete_postgresql_profiling_scan(
            db=db,
            scan_id=SCAN_ID,
        )

    assert scan.status != "completed" or override.get(
        "scan_status"
    ) == "completed"
    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_profiling_scan_completion_rejects_missing_scan() -> None:
    db, _ = make_completion_session()
    db.get.side_effect = lambda model, identity: None

    with pytest.raises(ValueError, match="Profiling scan not found"):
        complete_postgresql_profiling_scan(
            db=db,
            scan_id=SCAN_ID,
        )

    db.flush.assert_not_called()
    db.commit.assert_not_called()
