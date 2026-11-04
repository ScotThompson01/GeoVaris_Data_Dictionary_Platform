"""Opt-in PostgreSQL constraint tests for Phase 5E migration 0025.

Never uses the application DATABASE_URL or existing test databases.
Requires an explicit disposable database URL and opt-in flag.
"""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError


TABLE = "data_quality_execution_capacity_controls"


@pytest.fixture(scope="module")
def engine():
    if os.getenv("PHASE5E_DISPOSABLE_TEST") != "YES":
        pytest.skip("Disposable Phase 5E PostgreSQL test not enabled.")

    raw_url = os.getenv("PHASE5E_TEST_DATABASE_URL")

    if not raw_url:
        pytest.fail("Explicit Phase 5E test URL is required.")

    url = make_url(raw_url)

    if (
        url.host != "phase5e-postgres"
        or url.database != "phase5e_migration_test"
        or not url.drivername.startswith("postgresql")
    ):
        pytest.fail("Refusing non-disposable PostgreSQL database target.")

    db_engine = create_engine(raw_url, pool_pre_ping=True)

    try:
        with db_engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()

            assert revision == "0025"
        yield db_engine
    finally:
        db_engine.dispose()


def insert_control(connection, **changes):
    values = {
        "id": str(uuid4()),
        "scope_type": "installation",
        "data_source_id": None,
        "max_concurrent": 1,
    }
    values.update(changes)

    connection.execute(
        text(
            f"INSERT INTO {TABLE} "
            "(id, scope_type, data_source_id, max_concurrent) "
            "VALUES (:id, :scope_type, :data_source_id, :max_concurrent)"
        ),
        values,
    )


def assert_rejected(connection, sqlstate, **changes):
    with pytest.raises(IntegrityError) as error:
        with connection.begin_nested():
            insert_control(connection, **changes)

    assert error.value.orig.sqlstate == sqlstate


def test_invalid_capacity_scope_is_rejected(engine):
    with engine.begin() as connection:
        assert_rejected(
            connection, "23514",
            scope_type="invalid_scope",
        )
        connection.rollback()


def test_zero_capacity_limit_is_rejected(engine):
    with engine.begin() as connection:
        assert_rejected(
            connection, "23514",
            max_concurrent=0,
        )
        connection.rollback()


def test_source_control_requires_source_identity(engine):
    with engine.begin() as connection:
        assert_rejected(
            connection, "23514",
            scope_type="source",
            data_source_id=None,
        )
        connection.rollback()


def test_only_one_installation_control_is_allowed(engine):
    with engine.begin() as connection:
        insert_control(connection)

        assert_rejected(
            connection, "23505",
        )
        connection.rollback()


def test_reservation_null_guard_installed(engine):
    with engine.connect() as connection:
        definition = connection.execute(
            text(
                "SELECT pg_get_constraintdef(oid) "
                "FROM pg_constraint "
                "WHERE conname = 'ck_dq_reservation_source_scope' "
                "AND conrelid = "
                "'data_quality_execution_capacity_reservations'::regclass"
            )
        ).scalar_one()

    normalized = " ".join(definition.lower().split())

    assert "data_source_id is not null" in normalized
    assert "ownership_data_source_id" in normalized
