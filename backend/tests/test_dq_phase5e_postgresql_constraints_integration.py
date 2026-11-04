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


def _constraint_definition(connection, table_name, constraint_name):
    return connection.execute(
        text(
            "SELECT pg_get_constraintdef(c.oid) "
            "FROM pg_constraint AS c "
            "JOIN pg_class AS t ON t.oid = c.conrelid "
            "JOIN pg_namespace AS n ON n.oid = t.relnamespace "
            "WHERE n.nspname = 'public' "
            "AND t.relname = :table_name "
            "AND c.conname = :constraint_name"
        ),
        {
            "table_name": table_name,
            "constraint_name": constraint_name,
        },
    ).scalar_one()


def test_workload_composite_foreign_keys_installed(engine):
    required = {
        "fk_dq_workload_rule_field_identity": (
            "data_quality_rules",
            "rule_id, data_field_id",
        ),
        "fk_dq_workload_field_object_identity": (
            "data_fields",
            "data_field_id, source_object_id",
        ),
        "fk_dq_workload_source_object_identity": (
            "source_objects",
            "source_object_id, data_source_id",
        ),
        "fk_dq_workload_data_source_identity": (
            "data_sources",
            "data_source_id, project_id",
        ),
        "fk_dq_workload_execution_identity": (
            "data_quality_rule_executions",
            "execution_id, project_id, rule_id",
        ),
    }

    with engine.connect() as connection:
        for name, (target, columns) in required.items():
            definition = _constraint_definition(
                connection, "data_quality_workload_ownership", name
            )
            assert definition.startswith("FOREIGN KEY")
            assert f"({columns})" in definition
            assert f"REFERENCES {target}" in definition
            assert "ON DELETE RESTRICT" in definition


def test_reservation_composite_foreign_keys_installed(engine):
    required = {
        "fk_dq_reservation_ownership_source": (
            "ownership_id, ownership_data_source_id",
            "data_quality_workload_ownership",
        ),
        "fk_dq_reservation_capacity_source": (
            "capacity_control_id, reservation_scope, data_source_id",
            "data_quality_execution_capacity_controls",
        ),
        "fk_dq_reservation_capacity_scope": (
            "capacity_control_id, reservation_scope",
            "data_quality_execution_capacity_controls",
        ),
    }

    with engine.connect() as connection:
        for name, (columns, target) in required.items():
            definition = _constraint_definition(
                connection,
                "data_quality_execution_capacity_reservations",
                name,
            )
            assert definition.startswith("FOREIGN KEY")
            assert f"({columns})" in definition
            assert f"REFERENCES {target}" in definition
            assert "ON DELETE RESTRICT" in definition


def test_release_evidence_composite_foreign_keys_installed(engine):
    required = {
        "fk_dq_release_evidence_workload_identity": (
            "ownership_id, project_id, data_source_id",
            "data_quality_workload_ownership",
        ),
        "fk_dq_release_evidence_resolution_grant_identity": (
            "resolution_grant_id, project_id, actor_user_id",
            "data_quality_workload_resolution_grants",
        ),
    }

    with engine.connect() as connection:
        for name, (columns, target) in required.items():
            definition = _constraint_definition(
                connection, "data_quality_workload_release_evidence", name
            )
            assert definition.startswith("FOREIGN KEY")
            assert f"({columns})" in definition
            assert f"REFERENCES {target}" in definition
            assert "ON DELETE RESTRICT" in definition


def test_prerequisite_composite_unique_constraints_installed(engine):
    required = {
        "data_sources": (
            "uq_data_source_project_identity",
            "id, project_id",
        ),
        "source_objects": (
            "uq_source_object_source_identity",
            "id, data_source_id",
        ),
        "data_fields": (
            "uq_data_field_object_identity",
            "id, source_object_id",
        ),
        "data_quality_rules": (
            "uq_dq_rule_field_identity",
            "id, data_field_id",
        ),
        "data_quality_rule_executions": (
            "uq_dq_execution_project_rule_identity",
            "id, project_id, rule_id",
        ),
    }

    with engine.connect() as connection:
        for table_name, (name, columns) in required.items():
            definition = _constraint_definition(
                connection, table_name, name
            )
            assert definition == f"UNIQUE ({columns})"
