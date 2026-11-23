"""Rollback-only profiling persistence test for disposable PostgreSQL.

Requires explicit opt-in and the dedicated Phase 6C.2 test database.
Never runs against the main GeoVaris database.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.project import Project
from app.models.data_source import DataSource
from app.models.source_object import SourceObject
from app.models.data_field import DataField
from app.models.scan import Scan
from app.models.profiling_result import ProfilingResult
from app.profiling.database_profile import DatabaseFieldProfile
from app.services.postgresql_profiling_persistence import (
    complete_postgresql_profiling_scan,
    persist_postgresql_field_profile,
)


@pytest.mark.integration
def test_profiling_measurements_and_completion_rollback_together() -> None:
    if os.environ.get("GEOVARIS_PROFILE_INTEGRATION_TEST") != "1":
        pytest.skip("Isolated profiling integration test not enabled.")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.fail("DATABASE_URL is required.")

    target = make_url(database_url)

    if (
        target.drivername != "postgresql+psycopg"
        or target.host != "geovaris-pg-profile-test-1549"
        or target.port != 5432
        or target.database != "geovaris_profile_test"
        or target.username != "geovaris_profile_test"
    ):
        pytest.fail("Refusing non-isolated PostgreSQL database.")

    engine = create_engine(database_url, pool_pre_ping=True)

    scan_id = uuid.uuid4()
    field_id = uuid.uuid4()

    try:
        with engine.connect() as connection:
            transaction = connection.begin()

            try:
                with Session(
                    bind=connection,
                    join_transaction_mode="rollback_only",
                ) as db:
                    client_id = uuid.uuid4()
                    project_id = uuid.uuid4()
                    source_id = uuid.uuid4()
                    object_id = uuid.uuid4()

                    db.add(Client(
                        id=client_id,
                        name=f"Profiling synthetic {client_id.hex}",
                    ))
                    db.flush()

                    db.add(Project(
                        id=project_id,
                        client_id=client_id,
                        name="Synthetic profiling project",
                    ))
                    db.flush()

                    db.add(DataSource(
                        id=source_id,
                        project_id=project_id,
                        name="Synthetic PostgreSQL source",
                        source_type="postgresql",
                        connection_mode="read_only",
                    ))
                    db.flush()

                    db.add(SourceObject(
                        id=object_id,
                        data_source_id=source_id,
                        object_type="table",
                        schema_name="public",
                        object_name="synthetic_customers",
                    ))
                    db.flush()

                    db.add(DataField(
                        id=field_id,
                        source_object_id=object_id,
                        field_name="customer_id",
                        ordinal_position=1,
                    ))
                    db.flush()

                    db.add(Scan(
                        id=scan_id,
                        data_source_id=source_id,
                        scan_type="basic_profile",
                        status="running",
                    ))
                    db.flush()

                    profile = DatabaseFieldProfile(
                        schema_name="public",
                        object_name="synthetic_customers",
                        field_name="customer_id",
                        row_count=3_000_000_000,
                        null_count=300_000_000,
                        distinct_count=None,
                        minimum_value="100",
                        maximum_value="900",
                    )

                    result = persist_postgresql_field_profile(
                        db=db,
                        scan_id=scan_id,
                        data_field_id=field_id,
                        profile=profile,
                    )

                    assert result.row_count == 3_000_000_000
                    assert result.null_count == 300_000_000
                    assert result.distinct_count is None

                    with pytest.raises(ValueError, match="already exists"):
                        persist_postgresql_field_profile(
                            db=db,
                            scan_id=scan_id,
                            data_field_id=field_id,
                            profile=profile,
                        )

                    completed = complete_postgresql_profiling_scan(
                        db=db,
                        scan_id=scan_id,
                    )

                    assert completed.status == "completed"
                    assert completed.completed_at is not None

                    db.expire_all()

                    stored_result = db.scalar(
                        select(ProfilingResult).where(
                            ProfilingResult.scan_id == scan_id,
                            ProfilingResult.data_field_id == field_id,
                        )
                    )

                    stored_scan = db.get(Scan, scan_id)

                    assert stored_result is not None
                    assert stored_result.row_count == 3_000_000_000
                    assert stored_result.null_count == 300_000_000
                    assert stored_result.distinct_count is None
                    assert stored_result.distinct_percentage is None
                    assert stored_scan is not None
                    assert stored_scan.status == "completed"
                    assert stored_scan.completed_at is not None

            finally:
                transaction.rollback()

        with engine.connect() as verification:
            assert verification.scalar(
                select(ProfilingResult.id).where(
                    ProfilingResult.scan_id == scan_id
                )
            ) is None

            assert verification.scalar(
                select(Scan.id).where(Scan.id == scan_id)
            ) is None

    finally:
        engine.dispose()