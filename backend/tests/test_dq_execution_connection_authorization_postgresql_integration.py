"""PostgreSQL schema checks for execution authorization migration 0026.

Requires explicit opt-in and the dedicated disposable migration-test DB.
No client sources are accessed.
"""

import os

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import make_url


EXPECTED_HOST = "migration_test_db"
EXPECTED_PORT = 5432
EXPECTED_DATABASE = "geovaris_phase5e_migration_test"
EXPECTED_USER = "geovaris_migration_test"

TABLE = "data_quality_execution_connection_authorizations"


@pytest.fixture(scope="module")
def engine():
    if os.getenv("PHASE5E_0026_DISPOSABLE_TEST") != "YES":
        pytest.skip(
            "Explicit migration 0026 disposable-test opt-in required."
        )

    raw_url = os.getenv("PHASE5E_0026_TEST_DATABASE_URL")

    if not raw_url:
        pytest.fail("Explicit disposable migration-test URL required.")

    url = make_url(raw_url)

    if (
        url.drivername != "postgresql+psycopg"
        or url.host != EXPECTED_HOST
        or url.port != EXPECTED_PORT
        or url.database != EXPECTED_DATABASE
        or url.username != EXPECTED_USER
        or not url.password
        or url.query
    ):
        pytest.fail("Refusing non-approved PostgreSQL test target.")

    db_engine = create_engine(url, pool_pre_ping=True)

    try:
        with db_engine.connect() as connection:
            database, username = connection.execute(
                text("SELECT current_database(), current_user")
            ).one()

            if (
                database != EXPECTED_DATABASE
                or username != EXPECTED_USER
            ):
                pytest.fail(
                    "Connected PostgreSQL database identity mismatch."
                )

            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()

            if revision != "0026":
                pytest.fail(
                    "Disposable test database must be at revision 0026."
                )

        yield db_engine

    finally:
        db_engine.dispose()


def test_postgresql_authorization_columns_and_primary_key(engine):
    inspector = inspect(engine)

    columns = {
        column["name"]: column
        for column in inspector.get_columns(TABLE)
    }

    expected = {
        "execution_id",
        "project_id",
        "data_source_id",
        "connection_revision",
        "authorized_host",
        "authorized_port",
        "authorized_database",
        "authorized_ip",
        "authorized_at",
    }

    assert set(columns) == expected
    assert all(not columns[name]["nullable"] for name in expected)

    primary_key = inspector.get_pk_constraint(TABLE)

    assert primary_key["constrained_columns"] == ["execution_id"]


def test_postgresql_authorization_foreign_keys(engine):
    inspector = inspect(engine)

    foreign_keys = {
        key["name"]: key
        for key in inspector.get_foreign_keys(TABLE)
    }

    ownership = foreign_keys[
        "fk_dq_connection_auth_execution_source"
    ]

    assert ownership["referred_table"] == (
        "data_quality_workload_ownership"
    )

    assert ownership["constrained_columns"] == [
        "execution_id",
        "project_id",
        "data_source_id",
    ]

    assert ownership["referred_columns"] == [
        "execution_id",
        "project_id",
        "data_source_id",
    ]

    registered = foreign_keys[
        "fk_dq_connection_auth_registered_source"
    ]

    assert registered["referred_table"] == (
        "postgresql_connection_identities"
    )

    assert registered["constrained_columns"] == ["data_source_id"]
    assert registered["referred_columns"] == ["data_source_id"]

    unique_constraints = {
        constraint["name"]: constraint
        for constraint in inspector.get_unique_constraints(
            "data_quality_workload_ownership"
        )
    }

    composite = unique_constraints[
        "uq_dq_workload_execution_project_source"
    ]

    assert composite["column_names"] == [
        "execution_id",
        "project_id",
        "data_source_id",
    ]


def test_postgresql_authorization_check_constraints(engine):
    inspector = inspect(engine)

    checks = {
        constraint["name"]: constraint["sqltext"].lower()
        for constraint in inspector.get_check_constraints(TABLE)
    }

    revision = checks["ck_dq_connection_auth_positive_revision"]
    port = checks["ck_dq_connection_auth_valid_port"]

    assert "connection_revision" in revision
    assert ">=" in revision

    assert "authorized_port" in port
    assert "between" in port or (
        ">=" in port and "<=" in port
    )



# Transaction-scoped enforcement tests; never commit synthetic evidence.
_INVALID_AUTHORIZATION_INSERT = text("""
    INSERT INTO data_quality_execution_connection_authorizations (
        execution_id,
        project_id,
        data_source_id,
        connection_revision,
        authorized_host,
        authorized_port,
        authorized_database,
        authorized_ip,
        authorized_at
    ) VALUES (
        '00000000-0000-4000-8000-000000009101',
        '00000000-0000-4000-8000-000000009102',
        '00000000-0000-4000-8000-000000009103',
        :connection_revision,
        'synthetic.invalid',
        :authorized_port,
        'synthetic_db',
        '127.0.0.1',
        now()
    )
""")


@pytest.mark.parametrize(
    ("revision", "port", "expected_constraint"),
    [
        (0, 5432, "ck_dq_connection_auth_positive_revision"),
        (1, 0, "ck_dq_connection_auth_valid_port"),
        (1, 5432, "fk_dq_connection_auth_execution_source"),
    ],
)
def test_postgresql_authorization_rejects_invalid_revision(
    engine, revision, port, expected_constraint
):
    """Reject invalid synthetic evidence, with full transaction rollback."""
    with engine.connect() as connection:
        transaction = connection.begin()

        try:
            existing = connection.execute(
                text(
                    "SELECT COUNT(*) FROM "
                    "data_quality_execution_connection_authorizations"
                )
            ).scalar_one()
            assert existing == 0, "Disposable authorization table must be empty"

            # A savepoint isolates the expected database exception.
            with pytest.raises(IntegrityError) as error:
                with connection.begin_nested():
                    connection.execute(
                        _INVALID_AUTHORIZATION_INSERT,
                        {
                            "connection_revision": revision,
                            "authorized_port": port,
                        },
                    )

            assert (
                error.value.orig.diag.constraint_name
                == expected_constraint
            )

            remaining = connection.execute(
                text(
                    "SELECT COUNT(*) FROM "
                    "data_quality_execution_connection_authorizations"
                )
            ).scalar_one()
            assert remaining == 0

        finally:
            transaction.rollback()


def test_postgresql_authorization_linked_evidence(engine):
    """Verify linked evidence, mismatched source, and duplicate rejection.

    All records are synthetic and remain inside a rolled-back transaction.
    """
    identifiers = {
        "client": "00000000-0000-4000-8000-000000001101",
        "project": "00000000-0000-4000-8000-000000001102",
        "user": "00000000-0000-4000-8000-000000001103",
        "source_a": "00000000-0000-4000-8000-000000001104",
        "source_b": "00000000-0000-4000-8000-000000001105",
        "object": "00000000-0000-4000-8000-000000001106",
        "field": "00000000-0000-4000-8000-000000001107",
        "rule": "00000000-0000-4000-8000-000000001108",
        "version": "00000000-0000-4000-8000-000000001109",
        "execution": "00000000-0000-4000-8000-000000001110",
        "workload": "00000000-0000-4000-8000-000000001111",
    }

    tables = (
        "clients",
        "projects",
        "users",
        "data_sources",
        "source_objects",
        "data_fields",
        "data_quality_rules",
        "data_quality_rule_versions",
        "data_quality_rule_executions",
        "data_quality_workload_ownership",
        "postgresql_connection_identities",
        TABLE,
    )

    authorization_insert = text("""
        INSERT INTO data_quality_execution_connection_authorizations (
            execution_id, project_id, data_source_id,
            connection_revision, authorized_host, authorized_port,
            authorized_database, authorized_ip, authorized_at
        ) VALUES (
            :execution, :project, :source,
            1, :host, 5432, :database,
            :ip, now()
        )
    """)

    with engine.connect() as connection:
        transaction = connection.begin()

        try:
            connection.execute(text("SET LOCAL statement_timeout = '20s'"))
            connection.execute(text("SET LOCAL lock_timeout = '3s'"))

            # Do not introduce synthetic data into a nonempty database.
            for table in tables:
                assert connection.execute(
                    text(f"SELECT COUNT(*) FROM public.{table}")
                ).scalar_one() == 0, (
                    f"Disposable test table is not empty: {table}"
                )

            inserts = (
                (
                    "INSERT INTO clients (id, name) "
                    "VALUES (:client, 'phase5e-synthetic-client')"
                ),
                (
                    "INSERT INTO projects (id, client_id, name) "
                    "VALUES (:project, :client, 'phase5e-synthetic-project')"
                ),
                (
                    "INSERT INTO users (id, username, password_hash) "
                    "VALUES (:user, 'phase5e-synthetic-user', "
                    "'synthetic-nonfunctional-placeholder')"
                ),
                (
                    "INSERT INTO data_sources "
                    "(id, project_id, name, source_type, connection_mode) "
                    "VALUES (:source_a, :project, 'synthetic-source-a', "
                    "'postgresql', 'read_only')"
                ),
                (
                    "INSERT INTO data_sources "
                    "(id, project_id, name, source_type, connection_mode) "
                    "VALUES (:source_b, :project, 'synthetic-source-b', "
                    "'postgresql', 'read_only')"
                ),
                (
                    "INSERT INTO postgresql_connection_identities "
                    "(data_source_id, host, port, database_name, "
                    "connection_revision) "
                    "VALUES (:source_a, 'source-a.invalid', 5432, "
                    "'synthetic_a', 1)"
                ),
                (
                    "INSERT INTO postgresql_connection_identities "
                    "(data_source_id, host, port, database_name, "
                    "connection_revision) "
                    "VALUES (:source_b, 'source-b.invalid', 5432, "
                    "'synthetic_b', 1)"
                ),
                (
                    "INSERT INTO source_objects "
                    "(id, data_source_id, object_type, object_name) "
                    "VALUES (:object, :source_a, 'table', 'synthetic_object')"
                ),
                (
                    "INSERT INTO data_fields "
                    "(id, source_object_id, field_name, ordinal_position) "
                    "VALUES (:field, :object, 'synthetic_field', 1)"
                ),
                (
                    "INSERT INTO data_quality_rules "
                    "(id, data_field_id, rule_name) "
                    "VALUES (:rule, :field, 'synthetic-range-rule')"
                ),
                (
                    "INSERT INTO data_quality_rule_versions "
                    "(id, rule_id, version_number, rule_type, "
                    "quality_dimension, min_value, max_value) "
                    "VALUES (:version, :rule, 1, 'range', 'validity', 0, 100)"
                ),
                (
                    "INSERT INTO data_quality_rule_executions "
                    "(id, project_id, actor_user_id, rule_id, "
                    "version_id, status) "
                    "VALUES (:execution, :project, :user, :rule, "
                    ":version, 'pending')"
                ),
                (
                    "INSERT INTO data_quality_workload_ownership "
                    "(id, execution_id, project_id, rule_id, "
                    "data_field_id, source_object_id, data_source_id) "
                    "VALUES (:workload, :execution, :project, "
                    ":rule, :field, :object, :source_a)"
                ),
            )

            for statement in inserts:
                connection.execute(text(statement), identifiers)

            # Source B is registered but does not own this execution.
            with pytest.raises(IntegrityError) as mismatch:
                with connection.begin_nested():
                    connection.execute(
                        authorization_insert,
                        {
                            "execution": identifiers["execution"],
                            "project": identifiers["project"],
                            "source": identifiers["source_b"],
                            "host": "source-b.invalid",
                            "database": "synthetic_b",
                            "ip": "127.0.0.1",
                        },
                    )

            assert mismatch.value.orig.diag.constraint_name == (
                "fk_dq_connection_auth_execution_source"
            )

            # Correctly linked evidence must be accepted.
            valid = {
                "execution": identifiers["execution"],
                "project": identifiers["project"],
                "source": identifiers["source_a"],
                "host": "source-a.invalid",
                "database": "synthetic_a",
                "ip": "127.0.0.1",
            }

            connection.execute(authorization_insert, valid)

            assert connection.execute(
                text(
                    "SELECT COUNT(*) FROM "
                    "data_quality_execution_connection_authorizations"
                )
            ).scalar_one() == 1

            # A second authorization for the execution must be rejected.
            with pytest.raises(IntegrityError) as duplicate:
                with connection.begin_nested():
                    connection.execute(
                        authorization_insert,
                        {**valid, "ip": "127.0.0.2"},
                    )

            assert duplicate.value.orig.diag.constraint_name == (
                "data_quality_execution_connection_authorizations_pkey"
            )

            assert connection.execute(
                text(
                    "SELECT COUNT(*) FROM "
                    "data_quality_execution_connection_authorizations"
                )
            ).scalar_one() == 1

        finally:
            transaction.rollback()