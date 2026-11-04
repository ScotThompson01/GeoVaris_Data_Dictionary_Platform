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


def test_cross_source_reservation_is_rejected(engine):
    """A source reservation must match its workload's actual source."""
    ids = {
        name: str(uuid4())
        for name in (
            "client", "project", "user", "source_a", "source_b",
            "object", "field", "rule", "version", "execution",
            "ownership", "control_a", "control_b",
        )
    }

    def insert(connection, table, **values):
        columns = ", ".join(values)
        parameters = ", ".join(f":{column}" for column in values)
        connection.execute(
            text(
                f"INSERT INTO {table} ({columns}) "
                f"VALUES ({parameters})"
            ),
            values,
        )

    with engine.connect() as connection:
        transaction = connection.begin()

        try:
            insert(
                connection, "clients",
                id=ids["client"],
                name=f"Phase5E fixture {ids['client']}",
            )
            insert(
                connection, "projects",
                id=ids["project"],
                client_id=ids["client"],
                name="Phase5E isolated fixture",
            )
            insert(
                connection, "users",
                id=ids["user"],
                username=f"p5e_{ids['user'].replace('-', '')}",
                password_hash="fixture-only-not-a-login",
            )

            for name, source_name in (
                ("source_a", "Source A"),
                ("source_b", "Source B"),
            ):
                insert(
                    connection, "data_sources",
                    id=ids[name],
                    project_id=ids["project"],
                    name=source_name,
                    source_type="postgresql",
                    connection_mode="read_only",
                )

            insert(
                connection, "source_objects",
                id=ids["object"],
                data_source_id=ids["source_a"],
                object_type="table",
                object_name="fixture_table",
            )
            insert(
                connection, "data_fields",
                id=ids["field"],
                source_object_id=ids["object"],
                field_name="fixture_value",
                ordinal_position=1,
            )
            insert(
                connection, "data_quality_rules",
                id=ids["rule"],
                data_field_id=ids["field"],
                rule_name="Fixture range rule",
            )
            insert(
                connection, "data_quality_rule_versions",
                id=ids["version"],
                rule_id=ids["rule"],
                version_number=1,
                min_value=0,
                max_value=100,
            )
            insert(
                connection, "data_quality_rule_executions",
                id=ids["execution"],
                project_id=ids["project"],
                actor_user_id=ids["user"],
                rule_id=ids["rule"],
                version_id=ids["version"],
                status="pending",
            )
            # The field and object belong to Source A. An ownership
            # record claiming Source B must fail at the database layer.
            with pytest.raises(IntegrityError) as ownership_error:
                with connection.begin_nested():
                    insert(
                        connection,
                        "data_quality_workload_ownership",
                        id=str(uuid4()),
                        execution_id=ids["execution"],
                        project_id=ids["project"],
                        rule_id=ids["rule"],
                        data_field_id=ids["field"],
                        source_object_id=ids["object"],
                        data_source_id=ids["source_b"],
                    )

            assert ownership_error.value.orig.sqlstate == "23503"
            assert (
                ownership_error.value.orig.diag.constraint_name
                == "fk_dq_workload_source_object_identity"
            )

            insert(
                connection, "data_quality_workload_ownership",
                id=ids["ownership"],
                execution_id=ids["execution"],
                project_id=ids["project"],
                rule_id=ids["rule"],
                data_field_id=ids["field"],
                source_object_id=ids["object"],
                data_source_id=ids["source_a"],
            )

            for name, source_name in (
                ("control_a", "source_a"),
                ("control_b", "source_b"),
            ):
                insert(
                    connection,
                    "data_quality_execution_capacity_controls",
                    id=ids[name],
                    scope_type="source",
                    data_source_id=ids[source_name],
                    max_concurrent=1,
                )

            # This reservation references Source B capacity, but the
            # actual workload belongs to Source A.
            with pytest.raises(IntegrityError) as error:
                with connection.begin_nested():
                    insert(
                        connection,
                        "data_quality_execution_capacity_reservations",
                        id=str(uuid4()),
                        ownership_id=ids["ownership"],
                        capacity_control_id=ids["control_b"],
                        ownership_data_source_id=ids["source_a"],
                        data_source_id=ids["source_b"],
                        reservation_scope="source",
                    )

            assert error.value.orig.sqlstate == "23514"
            assert (
                error.value.orig.diag.constraint_name
                == "ck_dq_reservation_source_scope"
            )

            # Positive control: a matching reservation must succeed.
            insert(
                connection,
                "data_quality_execution_capacity_reservations",
                id=str(uuid4()),
                ownership_id=ids["ownership"],
                capacity_control_id=ids["control_a"],
                ownership_data_source_id=ids["source_a"],
                data_source_id=ids["source_a"],
                reservation_scope="source",
            )

            assert connection.execute(
                text(
                    "SELECT count(*) FROM "
                    "data_quality_execution_capacity_reservations "
                    "WHERE ownership_id = :ownership_id"
                ),
                {"ownership_id": ids["ownership"]},
            ).scalar_one() == 1

        finally:
            transaction.rollback()
