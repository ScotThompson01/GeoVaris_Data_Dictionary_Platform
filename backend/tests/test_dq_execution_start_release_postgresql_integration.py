"""Opt-in PostgreSQL concurrency tests for protected start and release.

Requires the dedicated disposable PostgreSQL database at revision 0026.
No client-source access, worker execution, or runtime admission.
"""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


EXPECTED_HOST = "migration_test_db"
EXPECTED_PORT = 5432
EXPECTED_DATABASE = "geovaris_phase5e_migration_test"
EXPECTED_USER = "geovaris_migration_test"


@pytest.fixture(scope="module")
def engine():
    if os.getenv("PHASE5E_0026_DISPOSABLE_TEST") != "YES":
        pytest.skip("Explicit disposable PostgreSQL opt-in required.")

    raw_url = os.getenv("PHASE5E_0026_TEST_DATABASE_URL")

    if not raw_url:
        pytest.fail("Explicit disposable PostgreSQL URL required.")

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
                pytest.fail("Connected PostgreSQL identity mismatch.")

            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()

            if revision != "0026":
                pytest.fail("Disposable database must be at revision 0026.")

        yield db_engine
    finally:
        db_engine.dispose()


def _synthetic_fixture_ids():
    """Generate unique identifiers for disposable test metadata."""
    from uuid import uuid4

    names = (
        "client",
        "project",
        "actor",
        "reviewer",
        "actor_membership",
        "reviewer_membership",
        "reviewer_session",
        "source",
        "object",
        "field",
        "rule",
        "version",
        "execution",
        "ownership",
        "installation_control",
        "source_control",
        "installation_reservation",
        "source_reservation",
        "resolution_grant",
        "release_evidence",
    )

    return {name: str(uuid4()) for name in names}


_SYNTHETIC_TABLES = frozenset({
    "clients",
    "projects",
    "users",
    "project_access",
    "auth_sessions",
    "data_sources",
    "source_objects",
    "data_fields",
    "data_quality_rules",
    "data_quality_rule_versions",
    "data_quality_execution_capacity_controls",
    "data_quality_workload_resolution_grants",
    "data_quality_workload_release_evidence",
})


def _insert_synthetic_record(connection, table, **values):
    """Insert synthetic fixture metadata using bound SQL parameters."""
    from sqlalchemy import text

    if table not in _SYNTHETIC_TABLES:
        raise ValueError("Table is not approved for synthetic fixtures.")

    if not values:
        raise ValueError("Synthetic insert requires column values.")

    if any(
        not name.isidentifier() or not name.isascii()
        for name in values
    ):
        raise ValueError("Invalid synthetic fixture column name.")

    columns = ", ".join(values)
    parameters = ", ".join(f":{name}" for name in values)

    connection.execute(
        text(
            f"INSERT INTO {table} ({columns}) "
            f"VALUES ({parameters})"
        ),
        values,
    )


def _insert_synthetic_client_project(connection, ids):
    """Stage an isolated synthetic client and project without committing."""
    _insert_synthetic_record(
        connection,
        "clients",
        id=ids["client"],
        name=f"Phase5E Synthetic Client {ids['client']}",
    )

    _insert_synthetic_record(
        connection,
        "projects",
        id=ids["project"],
        client_id=ids["client"],
        name=f"Phase5E Synthetic Project {ids['project']}",
    )


def _insert_synthetic_users_and_access(connection, ids):
    """Stage synthetic execution and reviewer identities without committing."""
    _insert_synthetic_record(
        connection,
        "users",
        id=ids["actor"],
        username=f"phase5e_actor_{ids['actor']}",
        password_hash="!synthetic-test-account-no-login!",
        is_active=True,
        is_installation_admin=False,
    )

    _insert_synthetic_record(
        connection,
        "users",
        id=ids["reviewer"],
        username=f"phase5e_reviewer_{ids['reviewer']}",
        password_hash="!synthetic-test-account-no-login!",
        is_active=True,
        is_installation_admin=True,
    )

    _insert_synthetic_record(
        connection,
        "project_access",
        id=ids["actor_membership"],
        user_id=ids["actor"],
        project_id=ids["project"],
        can_execute_dq_rules=True,
    )

    _insert_synthetic_record(
        connection,
        "project_access",
        id=ids["reviewer_membership"],
        user_id=ids["reviewer"],
        project_id=ids["project"],
    )


def _insert_synthetic_reviewer_session(connection, ids):
    """Stage a synthetic reviewer session and return its temporary token."""
    import secrets
    from datetime import datetime, timedelta, timezone

    from app.services.auth_sessions import _token_hash

    session_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=8)

    _insert_synthetic_record(
        connection,
        "auth_sessions",
        id=ids["reviewer_session"],
        user_id=ids["reviewer"],
        token_hash=_token_hash(session_token),
        expires_at=expires_at,
        revoked_at=None,
    )

    return session_token


def _insert_synthetic_data_source(connection, ids):
    """Stage source metadata only, without connecting to a source."""
    _insert_synthetic_record(
        connection,
        "data_sources",
        id=ids["source"],
        project_id=ids["project"],
        name=f"Phase5E Synthetic Source {ids['source']}",
        source_type="postgresql",
        connection_mode="read_only",
        is_active=True,
    )


def _insert_synthetic_source_object(connection, ids):
    """Stage fictional table metadata without accessing a source."""
    _insert_synthetic_record(
        connection,
        "source_objects",
        id=ids["object"],
        data_source_id=ids["source"],
        object_type="table",
        object_name=f"phase5e_fixture_{ids['object'].replace('-', '_')}",
        schema_name="synthetic",
    )


def _insert_synthetic_data_field(connection, ids):
    """Stage fictional field metadata without profiling source data."""
    _insert_synthetic_record(
        connection,
        "data_fields",
        id=ids["field"],
        source_object_id=ids["object"],
        field_name="fixture_value",
        ordinal_position=1,
        native_data_type="integer",
        normalized_data_type="integer",
        is_nullable=True,
    )


def _insert_synthetic_data_quality_rule(connection, ids):
    """Stage a draft rule identity without activating or executing it."""
    _insert_synthetic_record(
        connection,
        "data_quality_rules",
        id=ids["rule"],
        data_field_id=ids["field"],
        rule_name="Phase5E Synthetic Fixture Value Rule",
        status="draft",
        active_version_id=None,
    )


def _insert_synthetic_rule_version(connection, ids):
    """Stage a draft range-rule version without activating it."""
    _insert_synthetic_record(
        connection,
        "data_quality_rule_versions",
        id=ids["version"],
        rule_id=ids["rule"],
        created_by_user_id=ids["actor"],
        version_number=1,
        rule_type="range",
        quality_dimension="validity",
        min_value=0,
        max_value=100,
        null_allowed=True,
        status="draft",
    )


def _insert_synthetic_capacity_controls(connection, ids):
    """Stage capacity controls for an isolated disposable test database."""
    _insert_synthetic_record(
        connection,
        "data_quality_execution_capacity_controls",
        id=ids["installation_control"],
        scope_type="installation",
        data_source_id=None,
        max_concurrent=1,
    )
    _insert_synthetic_record(
        connection,
        "data_quality_execution_capacity_controls",
        id=ids["source_control"],
        scope_type="source",
        data_source_id=ids["source"],
        max_concurrent=1,
    )


def _insert_synthetic_resolution_grant(connection, ids):
    """Stage a test-only resolution grant for the synthetic reviewer."""
    _insert_synthetic_record(
        connection,
        "data_quality_workload_resolution_grants",
        id=ids["resolution_grant"],
        project_id=ids["project"],
        user_id=ids["reviewer"],
        granted_by_user_id=ids["reviewer"],
        revoked_at=None,
    )


def _insert_synthetic_release_evidence(connection, ids):
    """Stage test-only confirmed administrator-release evidence."""
    from sqlalchemy import text

    connection.execute(
        text(
            "INSERT INTO data_quality_workload_release_evidence "
            "(id, ownership_id, project_id, data_source_id, "
            "actor_user_id, resolution_grant_id, evidence_type, "
            "evidence_status, reason, evidence_reference, "
            "verified_by_user_id, verified_at) "
            "VALUES (:id, :ownership_id, :project_id, "
            ":data_source_id, :actor_user_id, :resolution_grant_id, "
            ":evidence_type, :evidence_status, :reason, "
            ":evidence_reference, :verified_by_user_id, now())"
        ),
        {
            "id": ids["release_evidence"],
            "ownership_id": ids["ownership"],
            "project_id": ids["project"],
            "data_source_id": ids["source"],
            "actor_user_id": ids["reviewer"],
            "resolution_grant_id": ids["resolution_grant"],
            "evidence_type": "authorized_admin_resolution",
            "evidence_status": "confirmed",
            "reason": "Synthetic administrator resolution for concurrency testing",
            "evidence_reference": (
                f"phase5e-synthetic-{ids['release_evidence']}"
            ),
            "verified_by_user_id": ids["reviewer"],
        },
    )


def _synthetic_prepared_metadata(ids):
    """Construct linked, in-memory metadata for protected admission."""
    from types import SimpleNamespace
    from uuid import UUID

    return {
        "rule": SimpleNamespace(
            id=UUID(ids["rule"]),
            data_field_id=UUID(ids["field"]),
        ),
        "version": SimpleNamespace(
            id=UUID(ids["version"]),
            rule_id=UUID(ids["rule"]),
        ),
        "field": SimpleNamespace(
            id=UUID(ids["field"]),
            source_object_id=UUID(ids["object"]),
        ),
        "source_object": SimpleNamespace(
            id=UUID(ids["object"]),
            data_source_id=UUID(ids["source"]),
        ),
        "source": SimpleNamespace(
            id=UUID(ids["source"]),
            project_id=UUID(ids["project"]),
        ),
    }


def _insert_synthetic_base_fixture(connection, ids):
    """Stage synthetic admission prerequisites in dependency order.

    The caller owns the transaction. No execution, ownership,
    reservations, or release evidence are inserted here.
    """
    _insert_synthetic_client_project(connection, ids)
    _insert_synthetic_users_and_access(connection, ids)
    reviewer_token = _insert_synthetic_reviewer_session(connection, ids)
    _insert_synthetic_data_source(connection, ids)
    _insert_synthetic_source_object(connection, ids)
    _insert_synthetic_data_field(connection, ids)
    _insert_synthetic_data_quality_rule(connection, ids)
    _insert_synthetic_rule_version(connection, ids)
    _insert_synthetic_capacity_controls(connection, ids)
    _insert_synthetic_resolution_grant(connection, ids)

    return reviewer_token


def _require_available_installation_capacity_control(connection):
    """Reject a conflicting installation control before fixture insertion."""
    from sqlalchemy import text

    existing_count = connection.execute(
        text(
            "SELECT count(*) "
            "FROM data_quality_execution_capacity_controls "
            "WHERE scope_type = :scope_type"
        ),
        {"scope_type": "installation"},
    ).scalar_one()

    if existing_count != 0:
        raise RuntimeError(
            "Disposable database already contains an installation "
            "capacity control; refusing synthetic fixture insertion."
        )


def _lock_synthetic_fixture_setup(connection):
    """Serialize cooperating synthetic fixture setups within a transaction.

    Caller must hold this lock through the installation-control
    preflight and fixture insertion, until commit or rollback.
    """
    from sqlalchemy import text

    connection.execute(
        text("SET LOCAL lock_timeout = '3s'")
    )
    connection.execute(
        text(
            "SELECT pg_advisory_xact_lock("
            "481516, 1496)"
        )
    )


def _stage_synthetic_fixture_prerequisites(connection, ids):
    """Stage synthetic prerequisites under the caller's transaction.

    The caller must use one transaction for locking, preflight,
    insertion, and commit. Roll back the entire transaction on error.
    """
    _lock_synthetic_fixture_setup(connection)
    _require_available_installation_capacity_control(connection)
    return _insert_synthetic_base_fixture(connection, ids)



def _delete_synthetic_release_evidence(connection, ids):
    """Delete only this fixture's release evidence; caller owns transaction."""
    connection.execute(
        text(
            "DELETE FROM data_quality_workload_release_evidence "
            "WHERE id = :id"
        ),
        {"id": ids["release_evidence"]},
    )


def _delete_synthetic_capacity_reservations(connection, ids):
    """Delete only this fixture's two reservations; caller owns transaction."""
    connection.execute(
        text(
            "DELETE FROM data_quality_execution_capacity_reservations "
            "WHERE id IN (:installation_id, :source_id)"
        ),
        {
            "installation_id": ids["installation_reservation"],
            "source_id": ids["source_reservation"],
        },
    )


def _delete_synthetic_workload_ownership(connection, ids):
    """Delete only this fixture's ownership; caller owns transaction."""
    connection.execute(
        text(
            "DELETE FROM data_quality_workload_ownership "
            "WHERE id = :id"
        ),
        {"id": ids["ownership"]},
    )


def _delete_synthetic_execution(connection, ids):
    """Delete only this fixture's execution; caller owns transaction."""
    connection.execute(
        text(
            "DELETE FROM data_quality_rule_executions "
            "WHERE id = :id"
        ),
        {"id": ids["execution"]},
    )


def _delete_synthetic_capacity_controls(connection, ids):
    """Delete only this fixture's capacity controls; caller owns transaction."""
    connection.execute(
        text(
            "DELETE FROM data_quality_execution_capacity_controls "
            "WHERE id IN (:installation_id, :source_id)"
        ),
        {
            "installation_id": ids["installation_control"],
            "source_id": ids["source_control"],
        },
    )


def _delete_synthetic_resolution_grant(connection, ids):
    """Delete only this fixture's resolution grant; caller owns transaction."""
    connection.execute(
        text(
            "DELETE FROM data_quality_workload_resolution_grants "
            "WHERE id = :id"
        ),
        {"id": ids["resolution_grant"]},
    )


def _delete_synthetic_reviewer_session(connection, ids):
    """Delete only this fixture's reviewer session; caller owns transaction."""
    connection.execute(
        text(
            "DELETE FROM auth_sessions "
            "WHERE id = :id"
        ),
        {"id": ids["reviewer_session"]},
    )


def _delete_synthetic_project_memberships(connection, ids):
    """Delete only this fixture's memberships; caller owns transaction."""
    connection.execute(
        text(
            "DELETE FROM project_access "
            "WHERE id IN (:actor_id, :reviewer_id)"
        ),
        {
            "actor_id": ids["actor_membership"],
            "reviewer_id": ids["reviewer_membership"],
        },
    )


def _delete_synthetic_rule_version(connection, ids):
    """Delete only this fixture's rule version; caller owns transaction."""
    connection.execute(
        text(
            "DELETE FROM data_quality_rule_versions "
            "WHERE id = :id"
        ),
        {"id": ids["version"]},
    )


def _delete_synthetic_data_quality_rule(connection, ids):
    """Delete only this fixture's Data Quality rule; caller owns transaction."""
    connection.execute(
        text(
            "DELETE FROM data_quality_rules "
            "WHERE id = :id"
        ),
        {"id": ids["rule"]},
    )


def _delete_synthetic_data_field(connection, ids):
    """Delete only this fixture's data field; caller owns transaction."""
    connection.execute(
        text(
            "DELETE FROM data_fields "
            "WHERE id = :id"
        ),
        {"id": ids["field"]},
    )


def _delete_synthetic_source_object(connection, ids):
    """Delete only this fixture's source object; caller owns transaction."""
    connection.execute(
        text(
            "DELETE FROM source_objects "
            "WHERE id = :id"
        ),
        {"id": ids["object"]},
    )


def _delete_synthetic_data_source(connection, ids):
    """Delete only this fixture's data source; caller owns transaction."""
    connection.execute(
        text(
            "DELETE FROM data_sources "
            "WHERE id = :id"
        ),
        {"id": ids["source"]},
    )


def _delete_synthetic_users(connection, ids):
    """Delete only this fixture's users; caller owns transaction."""
    connection.execute(
        text(
            "DELETE FROM users "
            "WHERE id IN (:actor_id, :reviewer_id)"
        ),
        {
            "actor_id": ids["actor"],
            "reviewer_id": ids["reviewer"],
        },
    )


def _delete_synthetic_project(connection, ids):
    """Delete only this fixture's project; caller owns transaction."""
    connection.execute(
        text(
            "DELETE FROM projects "
            "WHERE id = :id"
        ),
        {"id": ids["project"]},
    )


def _delete_synthetic_client(connection, ids):
    """Delete only this fixture's client; caller owns transaction."""
    connection.execute(
        text(
            "DELETE FROM clients "
            "WHERE id = :id"
        ),
        {"id": ids["client"]},
    )


def _capture_staged_cleanup_ids(ids, staged):
    """Capture actual generated IDs for fixture cleanup."""
    from uuid import UUID

    if not isinstance(ids, dict) or not isinstance(staged, dict):
        raise ValueError("Invalid cleanup identity metadata.")

    required = (
        "execution",
        "ownership",
        "installation_reservation",
        "source_reservation",
    )

    if any(staged.get(key) is None for key in required):
        raise ValueError("Incomplete staged cleanup records.")

    execution = staged["execution"]
    ownership = staged["ownership"]
    installation = staged["installation_reservation"]
    source = staged["source_reservation"]

    records = {
        "execution": execution,
        "ownership": ownership,
        "installation_reservation": installation,
        "source_reservation": source,
    }

    generated_ids = {}

    for name, record in records.items():
        record_id = getattr(record, "id", None)

        if not isinstance(record_id, UUID):
            raise ValueError(f"Invalid staged {name} identity.")

        generated_ids[name] = record_id

    if ownership.execution_id != generated_ids["execution"]:
        raise ValueError("Ownership execution identity mismatch.")

    if (
        installation.ownership_id != generated_ids["ownership"]
        or source.ownership_id != generated_ids["ownership"]
    ):
        raise ValueError("Reservation ownership identity mismatch.")

    result = dict(ids)
    result.update(generated_ids)

    return result


def _cleanup_synthetic_fixture(connection, ids):
    """Clean one synthetic fixture in dependency order.

    The caller owns the transaction. Any exception propagates so the
    transaction owner can roll back the complete cleanup operation.
    """
    if not isinstance(ids, dict):
        raise ValueError("Invalid synthetic cleanup identities.")

    required_ids = (
        "release_evidence",
        "installation_reservation",
        "source_reservation",
        "ownership",
        "execution",
        "installation_control",
        "source_control",
        "resolution_grant",
        "reviewer_session",
        "actor_membership",
        "reviewer_membership",
        "version",
        "rule",
        "field",
        "object",
        "source",
        "actor",
        "reviewer",
        "project",
        "client",
    )

    if any(ids.get(key) is None for key in required_ids):
        raise ValueError("Incomplete synthetic cleanup identities.")

    cleanup_steps = (
        _delete_synthetic_release_evidence,
        _delete_synthetic_capacity_reservations,
        _delete_synthetic_workload_ownership,
        _delete_synthetic_execution,
        _delete_synthetic_capacity_controls,
        _delete_synthetic_resolution_grant,
        _delete_synthetic_reviewer_session,
        _delete_synthetic_project_memberships,
        _delete_synthetic_rule_version,
        _delete_synthetic_data_quality_rule,
        _delete_synthetic_data_field,
        _delete_synthetic_source_object,
        _delete_synthetic_data_source,
        _delete_synthetic_users,
        _delete_synthetic_project,
        _delete_synthetic_client,
    )

    for cleanup_step in cleanup_steps:
        cleanup_step(connection, ids)

    return len(cleanup_steps)


def test_protected_admission_fixture_lifecycle(engine):
    """Verify protected admission and exact-ID cleanup atomically."""
    from uuid import UUID

    from sqlalchemy import text
    from sqlalchemy.orm import Session

    # Register the complete ORM dependency graph before flushing.
    from app.models import data_quality_rule
    from app.models import data_quality_rule_version
    from app.models import data_quality_rule_execution
    from app.models import data_quality_workload_ownership
    from app.models import data_quality_execution_capacity_control
    from app.models import data_quality_execution_capacity_reservation
    from app.models import data_quality_workload_resolution_grant
    from app.models import data_quality_workload_release_evidence

    from app.services.data_quality_execution_admission_staging import (
        stage_protected_execution_records,
    )

    ids = _synthetic_fixture_ids()
    db = Session(engine, autoflush=False)

    try:
        # One connection and one caller-owned transaction.
        connection = db.connection()

        reviewer_token = _stage_synthetic_fixture_prerequisites(
            connection,
            ids,
        )
        assert isinstance(reviewer_token, str) and reviewer_token

        prepared = _synthetic_prepared_metadata(ids)

        staged = stage_protected_execution_records(
            db,
            prepared=prepared,
            project_id=UUID(ids["project"]),
            actor_user_id=UUID(ids["actor"]),
            installation_limit=1,
        )

        assert staged["execution"].status == "pending"

        cleanup_ids = _capture_staged_cleanup_ids(ids, staged)

        assert len({
            cleanup_ids["execution"],
            cleanup_ids["ownership"],
            cleanup_ids["installation_reservation"],
            cleanup_ids["source_reservation"],
        }) == 4

        _insert_synthetic_release_evidence(
            connection,
            cleanup_ids,
        )

        # Verify admission and release-evidence records.
        checks = (
            (
                "SELECT status FROM data_quality_rule_executions "
                "WHERE id = :id",
                cleanup_ids["execution"],
                "pending",
            ),
            (
                "SELECT ownership_state "
                "FROM data_quality_workload_ownership WHERE id = :id",
                cleanup_ids["ownership"],
                "reserved",
            ),
            (
                "SELECT evidence_status "
                "FROM data_quality_workload_release_evidence WHERE id = :id",
                cleanup_ids["release_evidence"],
                "confirmed",
            ),
        )

        for sql, identity, expected in checks:
            actual = connection.execute(
                text(sql),
                {"id": identity},
            ).scalar_one()

            assert actual == expected

        reservation_count = connection.execute(
            text(
                "SELECT count(*) "
                "FROM data_quality_execution_capacity_reservations "
                "WHERE ownership_id = :id "
                "AND reservation_state = 'reserved'"
            ),
            {"id": cleanup_ids["ownership"]},
        ).scalar_one()

        assert reservation_count == 2

        # Exact-ID cleanup within the same transaction.
        assert _cleanup_synthetic_fixture(
            connection,
            cleanup_ids,
        ) == 16

        # Raw SQL cleanup bypasses ORM identity-map synchronization.
        db.expire_all()

        cleanup_targets = (
            ("clients", "client"),
            ("projects", "project"),
            ("users", "actor"),
            ("users", "reviewer"),
            ("project_access", "actor_membership"),
            ("project_access", "reviewer_membership"),
            ("auth_sessions", "reviewer_session"),
            ("data_sources", "source"),
            ("source_objects", "object"),
            ("data_fields", "field"),
            ("data_quality_rules", "rule"),
            ("data_quality_rule_versions", "version"),
            ("data_quality_rule_executions", "execution"),
            ("data_quality_workload_ownership", "ownership"),
            ("data_quality_execution_capacity_controls",
             "installation_control"),
            ("data_quality_execution_capacity_controls", "source_control"),
            ("data_quality_execution_capacity_reservations",
             "installation_reservation"),
            ("data_quality_execution_capacity_reservations",
             "source_reservation"),
            ("data_quality_workload_resolution_grants",
             "resolution_grant"),
            ("data_quality_workload_release_evidence", "release_evidence"),
        )

        for table, identity in cleanup_targets:
            remaining = connection.execute(
                text(f"SELECT count(*) FROM {table} WHERE id = :id"),
                {"id": cleanup_ids[identity]},
            ).scalar_one()

            assert remaining == 0, (
                f"Synthetic record remains: {table}/{identity}"
            )

        # Commit only after all assertions and cleanup succeed.
        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
