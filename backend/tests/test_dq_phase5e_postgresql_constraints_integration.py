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



def _phase5e_fixture_ids():
    """Create unique identifiers for isolated PostgreSQL fixtures."""
    return {
        name: str(uuid4())
        for name in (
            "client", "project", "project_b", "user", "user_b",
            "source_a", "source_b", "object", "field",
            "rule", "version", "execution", "ownership",
            "control_a", "control_b", "grant",
        )
    }


def test_cross_source_reservation_is_rejected(engine):
    """A source reservation must match its workload's actual source."""
    ids = _phase5e_fixture_ids()

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
                connection, "projects",
                id=ids["project_b"],
                client_id=ids["client"],
                name="Phase5E separate project",
            )
            insert(
                connection, "users",
                id=ids["user"],
                username=f"p5e_{ids['user'].replace('-', '')}",
                password_hash="fixture-only-not-a-login",
            )
            insert(
                connection, "users",
                id=ids["user_b"],
                username=f"p5e_{ids['user_b'].replace('-', '')}",
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
            # An execution and source belonging to Project A cannot
            # be assigned to a workload claiming Project B.
            with pytest.raises(IntegrityError) as project_error:
                with connection.begin_nested():
                    insert(
                        connection,
                        "data_quality_workload_ownership",
                        id=str(uuid4()),
                        execution_id=ids["execution"],
                        project_id=ids["project_b"],
                        rule_id=ids["rule"],
                        data_field_id=ids["field"],
                        source_object_id=ids["object"],
                        data_source_id=ids["source_a"],
                    )

            assert project_error.value.orig.sqlstate == "23503"
            assert project_error.value.orig.diag.constraint_name in {
                "fk_dq_workload_data_source_identity",
                "fk_dq_workload_execution_identity",
            }

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

            # The grant belongs to User A in Project A.
            insert(
                connection,
                "data_quality_workload_resolution_grants",
                id=ids["grant"],
                project_id=ids["project"],
                user_id=ids["user"],
                granted_by_user_id=ids["user"],
            )

            def insert_evidence(**changes):
                values = {
                    "id": str(uuid4()),
                    "ownership_id": ids["ownership"],
                    "project_id": ids["project"],
                    "data_source_id": ids["source_a"],
                    "actor_user_id": ids["user"],
                    "resolution_grant_id": ids["grant"],
                    "evidence_type": "authorized_admin_resolution",
                    "reason": "Isolated identity constraint test",
                    "evidence_reference": "phase5e-test-reference",
                }
                values.update(changes)
                insert(
                    connection,
                    "data_quality_workload_release_evidence",
                    **values,
                )

            # Evidence cannot claim another project's identity.
            with pytest.raises(IntegrityError) as project_evidence_error:
                with connection.begin_nested():
                    insert_evidence(
                        project_id=ids["project_b"],
                    )

            assert project_evidence_error.value.orig.sqlstate == "23503"
            assert (
                project_evidence_error.value.orig.diag.constraint_name
                in {
                    "fk_dq_release_evidence_workload_identity",
                    "fk_dq_release_evidence_resolution_grant_identity",
                }
            )

            # User B cannot use User A's resolution grant.
            with pytest.raises(IntegrityError) as actor_evidence_error:
                with connection.begin_nested():
                    insert_evidence(
                        actor_user_id=ids["user_b"],
                    )

            assert actor_evidence_error.value.orig.sqlstate == "23503"
            assert (
                actor_evidence_error.value.orig.diag.constraint_name
                == "fk_dq_release_evidence_resolution_grant_identity"
            )

            # Matching identities must be accepted by the database.
            insert_evidence()

            evidence_count = connection.execute(
                text(
                    "SELECT count(*) "
                    "FROM data_quality_workload_release_evidence "
                    "WHERE ownership_id = :ownership_id"
                ),
                {"ownership_id": ids["ownership"]},
            ).scalar_one()

            assert evidence_count == 1

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



def test_persisted_administrator_release_is_atomic(engine):
    """Real PostgreSQL authorization checks must preserve reserved capacity."""
    from sqlalchemy.orm import Session
    from datetime import datetime, timedelta, timezone
    from secrets import token_urlsafe

    from app.services.auth_sessions import _token_hash

    # Register all ORM tables before SQLAlchemy computes flush dependencies.
    import app.db.base  # noqa: F401

    from app.services.data_quality_persisted_admin_release_transaction import (
        stage_persisted_admin_resolution,
    )

    ids = {
        name: str(uuid4())
        for name in (
            "client", "project", "user", "source", "object", "field",
            "rule", "version", "execution", "ownership",
            "installation", "source_control", "installation_reservation",
            "source_reservation", "grant", "membership", "evidence",
            "reviewer", "reviewer_membership",
        )
    }

    def insert(connection, table, **values):
        columns = ", ".join(values)
        parameters = ", ".join(f":{name}" for name in values)
        connection.execute(
            text(
                f"INSERT INTO {table} ({columns}) "
                f"VALUES ({parameters})"
            ),
            values,
        )

    def assert_protected(connection):
        state = connection.execute(
            text(
                "SELECT ownership_state FROM "
                "data_quality_workload_ownership WHERE id = :id"
            ),
            {"id": ids["ownership"]},
        ).scalar_one()

        reservations = connection.execute(
            text(
                "SELECT reservation_state FROM "
                "data_quality_execution_capacity_reservations "
                "WHERE ownership_id = :id ORDER BY reservation_scope"
            ),
            {"id": ids["ownership"]},
        ).scalars().all()

        assert state == "unresolved"
        assert reservations == ["unresolved", "unresolved"]

    with engine.connect() as connection:
        transaction = connection.begin()
        session = None

        try:
            insert(
                connection, "clients",
                id=ids["client"],
                name=f"Phase5E release {ids['client']}",
            )
            insert(
                connection, "projects",
                id=ids["project"],
                client_id=ids["client"],
                name="Disposable release project",
            )
            insert(
                connection, "users",
                id=ids["user"],
                username=f"p5e_{ids['user'].replace('-', '')}",
                password_hash="fixture-only-not-a-login",
            )

            # Disposable authentication session for the release actor.
            # Only its hash is persisted, and the entire fixture rolls back.
            session_token = token_urlsafe(32)

            insert(
                connection, "auth_sessions",
                id=str(uuid4()),
                user_id=ids["user"],
                token_hash=_token_hash(session_token),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )

            insert(
                connection, "project_access",
                id=ids["membership"],
                project_id=ids["project"],
                user_id=ids["user"],
            )
            insert(
                connection, "users",
                id=ids["reviewer"],
                username=f"p5e_{ids['reviewer'].replace('-', '')}",
                password_hash="fixture-only-not-a-login",
                is_active=True,
                is_installation_admin=True,
            )
            insert(
                connection, "project_access",
                id=ids["reviewer_membership"],
                project_id=ids["project"],
                user_id=ids["reviewer"],
            )
            insert(
                connection, "data_sources",
                id=ids["source"],
                project_id=ids["project"],
                name="Disposable read-only source",
                source_type="postgresql",
                connection_mode="read_only",
            )
            insert(
                connection, "source_objects",
                id=ids["object"],
                data_source_id=ids["source"],
                object_type="table",
                object_name="release_fixture",
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
                rule_name="Disposable release rule",
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
            insert(
                connection, "data_quality_workload_ownership",
                id=ids["ownership"],
                execution_id=ids["execution"],
                project_id=ids["project"],
                rule_id=ids["rule"],
                data_field_id=ids["field"],
                source_object_id=ids["object"],
                data_source_id=ids["source"],
                ownership_state="unresolved",
            )

            insert(
                connection,
                "data_quality_execution_capacity_controls",
                id=ids["installation"],
                scope_type="installation",
                data_source_id=None,
                max_concurrent=1,
            )
            insert(
                connection,
                "data_quality_execution_capacity_controls",
                id=ids["source_control"],
                scope_type="source",
                data_source_id=ids["source"],
                max_concurrent=1,
            )

            for scope, control_id, source_id, reservation_id in (
                (
                    "installation", ids["installation"], None,
                    ids["installation_reservation"],
                ),
                (
                    "source", ids["source_control"], ids["source"],
                    ids["source_reservation"],
                ),
            ):
                insert(
                    connection,
                    "data_quality_execution_capacity_reservations",
                    id=reservation_id,
                    ownership_id=ids["ownership"],
                    capacity_control_id=control_id,
                    ownership_data_source_id=ids["source"],
                    data_source_id=source_id,
                    reservation_scope=scope,
                    reservation_state="unresolved",
                )

            insert(
                connection,
                "data_quality_workload_resolution_grants",
                id=ids["grant"],
                project_id=ids["project"],
                user_id=ids["user"],
                granted_by_user_id=ids["user"],
            )

            connection.execute(
                text(
                    "INSERT INTO data_quality_workload_release_evidence "
                    "(id, ownership_id, project_id, data_source_id, "
                    "actor_user_id, resolution_grant_id, evidence_type, "
                    "evidence_status, reason, evidence_reference, "
                    "verified_by_user_id, verified_at) "
                    "VALUES (:id, :ownership_id, :project_id, "
                    ":data_source_id, :actor_user_id, :grant_id, "
                    "'authorized_admin_resolution', 'confirmed', "
                    ":reason, :reference, :reviewer_id, now())"
                ),
                {
                    "id": ids["evidence"],
                    "ownership_id": ids["ownership"],
                    "project_id": ids["project"],
                    "data_source_id": ids["source"],
                    "actor_user_id": ids["user"],
                    "grant_id": ids["grant"],
                    "reason": "Reviewed administrator resolution",
                    "reference": "disposable-admin-evidence",
                    "reviewer_id": ids["reviewer"],
                },
            )

            session = Session(
                bind=connection,
                autoflush=False,
                join_transaction_mode="rollback_only",
            )

            kwargs = {
                "project_id": uuid4(),
                "ownership_id": uuid4(),
                "data_source_id": uuid4(),
                "evidence_id": uuid4(),
                "trusted_actor_user_id": uuid4(),
                "session_token": session_token,
                "reason": "Reviewed administrator resolution",
                "evidence_reference": "disposable-admin-evidence",
            }

            from uuid import UUID

            kwargs.update({
                "project_id": UUID(ids["project"]),
                "ownership_id": UUID(ids["ownership"]),
                "data_source_id": UUID(ids["source"]),
                "evidence_id": UUID(ids["evidence"]),
                "trusted_actor_user_id": UUID(ids["user"]),
            })

            assert_protected(connection)

            # A revoked grant cannot authorize release.
            with connection.begin_nested() as savepoint:
                connection.execute(
                    text(
                        "UPDATE data_quality_workload_resolution_grants "
                        "SET revoked_at = now() WHERE id = :id"
                    ),
                    {"id": ids["grant"]},
                )
                with pytest.raises(ValueError, match="Active administrator"):
                    stage_persisted_admin_resolution(session, **kwargs)
                assert_protected(connection)
                session.close()
                savepoint.rollback()
                session = Session(
                    bind=connection,
                    autoflush=False,
                    join_transaction_mode="rollback_only",
                )

            # Removing project membership must also prevent release.
            with connection.begin_nested() as savepoint:
                connection.execute(
                    text("DELETE FROM project_access WHERE id = :id"),
                    {"id": ids["membership"]},
                )
                with pytest.raises(ValueError, match="membership"):
                    stage_persisted_admin_resolution(session, **kwargs)
                assert_protected(connection)
                session.close()
                savepoint.rollback()
                session = Session(
                    bind=connection,
                    autoflush=False,
                    join_transaction_mode="rollback_only",
                )

            # Unconfirmed evidence must not release capacity.
            with connection.begin_nested() as savepoint:
                connection.execute(
                    text(
                        "UPDATE data_quality_workload_release_evidence "
                        "SET evidence_status = 'recorded', "
                        "verified_at = NULL, verified_by_user_id = NULL "
                        "WHERE id = :id"
                    ),
                    {"id": ids["evidence"]},
                )
                with pytest.raises(ValueError, match="not been confirmed"):
                    stage_persisted_admin_resolution(session, **kwargs)
                assert_protected(connection)
                session.close()
                savepoint.rollback()
                session = Session(
                    bind=connection,
                    autoflush=False,
                    join_transaction_mode="rollback_only",
                )

            # An actor mismatch must not release capacity.
            with pytest.raises(ValueError, match="Trusted actor"):
                stage_persisted_admin_resolution(
                    session,
                    **{
                        **kwargs,
                        "trusted_actor_user_id": uuid4(),
                    },
                )
            assert_protected(connection)

            # Disabling the resolution actor must reject release even
            # while their project membership and dedicated grant remain.
            with connection.begin_nested() as savepoint:
                connection.execute(
                    text(
                        "UPDATE users SET is_active = FALSE WHERE id = :id"
                    ),
                    {"id": ids["user"]},
                )

                with pytest.raises(
                    ValueError,
                    match="Active resolution actor account required",
                ):
                    stage_persisted_admin_resolution(session, **kwargs)

                assert_protected(connection)
                session.close()
                savepoint.rollback()
                session = Session(
                    bind=connection,
                    autoflush=False,
                    join_transaction_mode="rollback_only",
                )

            # Reviewer must remain active, an installation administrator,
            # and a current member of this project. The actor is a
            # separate user so its own authorization remains intact.
            for mutation, parameters, expected_error in (
                (
                    "UPDATE users SET is_active = FALSE WHERE id = :id",
                    {"id": ids["reviewer"]},
                    "Active installation administrator",
                ),
                (
                    "UPDATE users SET is_installation_admin = FALSE "
                    "WHERE id = :id",
                    {"id": ids["reviewer"]},
                    "Active installation administrator",
                ),
                (
                    "DELETE FROM project_access WHERE id = :id",
                    {"id": ids["reviewer_membership"]},
                    "Reviewer project membership",
                ),
            ):
                with connection.begin_nested() as savepoint:
                    connection.execute(text(mutation), parameters)
                    with pytest.raises(ValueError, match=expected_error):
                        stage_persisted_admin_resolution(session, **kwargs)
                    assert_protected(connection)
                    session.close()
                    savepoint.rollback()
                    session = Session(
                        bind=connection,
                        autoflush=False,
                        join_transaction_mode="rollback_only",
                    )

            # Revoked and expired authentication sessions must not
            # release capacity, even when all grants remain valid.
            for mutation in (
                "UPDATE auth_sessions SET revoked_at = now() "
                "WHERE token_hash = :token_hash",
                "UPDATE auth_sessions "
                "SET expires_at = now() - interval '1 hour' "
                "WHERE token_hash = :token_hash",
            ):
                with connection.begin_nested() as savepoint:
                    connection.execute(
                        text(mutation),
                        {"token_hash": _token_hash(session_token)},
                    )

                    with pytest.raises(
                        PermissionError,
                        match="authenticated release session",
                    ):
                        stage_persisted_admin_resolution(
                            session, **kwargs
                        )

                    assert_protected(connection)
                    session.close()
                    savepoint.rollback()

                    session = Session(
                        bind=connection,
                        autoflush=False,
                        join_transaction_mode="rollback_only",
                    )

            # Matching confirmed evidence, active authorization, and
            # a live authenticated session may stage release atomically.
            stage_persisted_admin_resolution(session, **kwargs)

            ownership_state = connection.execute(
                text(
                    "SELECT ownership_state FROM "
                    "data_quality_workload_ownership WHERE id = :id"
                ),
                {"id": ids["ownership"]},
            ).scalar_one()

            reservation_states = connection.execute(
                text(
                    "SELECT reservation_state FROM "
                    "data_quality_execution_capacity_reservations "
                    "WHERE ownership_id = :id ORDER BY reservation_scope"
                ),
                {"id": ids["ownership"]},
            ).scalars().all()

            assert ownership_state == "released"
            assert reservation_states == ["released", "released"]

        finally:
            if session is not None:
                session.close()
            transaction.rollback()


def test_concurrent_session_revocation_blocks_locked_validation(engine):
    """Validation must wait for revocation and reject the committed result."""
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime, timedelta, timezone
    from secrets import token_urlsafe
    from threading import Event
    from time import monotonic, sleep
    from uuid import UUID

    from sqlalchemy.orm import Session

    import app.db.base  # noqa: F401

    from app.services.auth_sessions import _token_hash
    from app.services.data_quality_locked_release_session import (
        require_locked_release_session,
    )

    actor_id = uuid4()
    token = token_urlsafe(32)
    token_hash = _token_hash(token)
    session_id = uuid4()
    worker_started = Event()
    worker_pids = []

    # This test uses only its own records in the disposable database.
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, username, password_hash) "
                "VALUES (:id, :username, :password_hash)"
            ),
            {
                "id": str(actor_id),
                "username": f"p5e_race_{actor_id.hex}",
                "password_hash": "disposable-fixture-only",
            },
        )
        connection.execute(
            text(
                "INSERT INTO auth_sessions "
                "(id, user_id, token_hash, expires_at) "
                "VALUES (:id, :user_id, :token_hash, :expires_at)"
            ),
            {
                "id": str(session_id),
                "user_id": str(actor_id),
                "token_hash": token_hash,
                "expires_at": (
                    datetime.now(timezone.utc) + timedelta(hours=1)
                ),
            },
        )

    try:
        def validate_in_worker():
            with Session(engine, autoflush=False) as session:
                session.execute(
                    text("SET LOCAL lock_timeout = '5s'")
                )
                backend_pid = session.execute(
                    text("SELECT pg_backend_pid()")
                ).scalar_one()
                worker_pids.append(backend_pid)
                worker_started.set()

                try:
                    require_locked_release_session(
                        session,
                        session_token=token,
                        expected_actor_user_id=UUID(str(actor_id)),
                    )
                except PermissionError:
                    return backend_pid, "rejected"

                return backend_pid, "accepted"

        with engine.connect() as revoker:
            transaction = revoker.begin()

            try:
                revoker_pid = revoker.execute(
                    text("SELECT pg_backend_pid()")
                ).scalar_one()

                revoker.execute(
                    text(
                        "UPDATE auth_sessions SET revoked_at = now() "
                        "WHERE id = :id"
                    ),
                    {"id": str(session_id)},
                )

                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(validate_in_worker)

                    assert worker_started.wait(timeout=5), (
                        "Session validation worker did not start"
                    )

                    # Require proof that PostgreSQL actually blocked the
                    # validator on the revocation transaction's row lock.
                    deadline = monotonic() + 4
                    observed_lock_wait = False

                    while monotonic() < deadline:
                        blockers = revoker.execute(
                            text(
                                "SELECT pg_blocking_pids(:worker_pid)"
                            ),
                            {"worker_pid": worker_pids[0]},
                        ).scalar_one()

                        if revoker_pid in blockers:
                            observed_lock_wait = True
                            break

                        if future.done():
                            # Surface an early worker exception directly,
                            # rather than reporting a misleading lock failure.
                            future.result()
                            break

                        sleep(0.05)

                    assert observed_lock_wait, (
                        "Validator did not visibly wait on the session lock"
                    )
                    assert not future.done(), (
                        "Validator finished before revocation committed"
                    )

                    transaction.commit()
                    _, outcome = future.result(timeout=6)

                    assert outcome == "rejected", (
                        "Revoked session unexpectedly passed validation"
                    )

            finally:
                if transaction.is_active:
                    transaction.rollback()

    finally:
        with engine.begin() as cleanup:
            cleanup.execute(
                text("DELETE FROM auth_sessions WHERE id = :id"),
                {"id": str(session_id)},
            )
            cleanup.execute(
                text("DELETE FROM users WHERE id = :id"),
                {"id": str(actor_id)},
            )



def test_capacity_admission_locks_both_controls(engine):
    """Installation and source locks must survive through the transaction."""
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session

    from app.services.data_quality_execution_admission_capacity import (
        require_locked_execution_capacity,
    )

    ids = {
        key: uuid4()
        for key in (
            "client", "project", "source",
            "installation_control", "source_control",
        )
    }

    # Synthetic records exist only in the opt-in disposable test database.
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO clients (id, name) VALUES (:id, :name)"),
            {
                "id": str(ids["client"]),
                "name": "Disposable capacity-locking client",
            },
        )
        connection.execute(
            text(
                "INSERT INTO projects (id, client_id, name) "
                "VALUES (:id, :client_id, :name)"
            ),
            {
                "id": str(ids["project"]),
                "client_id": str(ids["client"]),
                "name": "Disposable capacity-locking project",
            },
        )
        connection.execute(
            text(
                "INSERT INTO data_sources "
                "(id, project_id, name, source_type, connection_mode) "
                "VALUES (:id, :project_id, :name, "
                "'postgresql', 'read_only')"
            ),
            {
                "id": str(ids["source"]),
                "project_id": str(ids["project"]),
                "name": "Disposable capacity-locking source",
            },
        )
        connection.execute(
            text(
                "INSERT INTO data_quality_execution_capacity_controls "
                "(id, scope_type, data_source_id, max_concurrent) "
                "VALUES (:id, 'installation', NULL, 2)"
            ),
            {"id": str(ids["installation_control"])},
        )
        connection.execute(
            text(
                "INSERT INTO data_quality_execution_capacity_controls "
                "(id, scope_type, data_source_id, max_concurrent) "
                "VALUES (:id, 'source', :source_id, 1)"
            ),
            {
                "id": str(ids["source_control"]),
                "source_id": str(ids["source"]),
            },
        )

    try:
        with Session(engine, autoflush=False) as first:
            installation, source = require_locked_execution_capacity(
                first,
                data_source_id=ids["source"],
                installation_limit=2,
            )

            assert installation.id == ids["installation_control"]
            assert source.id == ids["source_control"]

            # A second transaction must not acquire either row lock.
            with engine.connect() as second:
                for control_id in (
                    ids["installation_control"],
                    ids["source_control"],
                ):
                    with pytest.raises(OperationalError) as error:
                        with second.begin():
                            second.execute(
                                text("SET LOCAL lock_timeout = '300ms'")
                            )
                            second.execute(
                                text(
                                    "SELECT id FROM "
                                    "data_quality_execution_capacity_controls "
                                    "WHERE id = :id FOR UPDATE"
                                ),
                                {"id": str(control_id)},
                            ).scalar_one()

                    assert (
                        getattr(error.value.orig, "sqlstate", None)
                        == "55P03"
                    )

            # Neither test nor capacity service commits admission.
            first.rollback()

    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM "
                    "data_quality_execution_capacity_controls "
                    "WHERE id IN (:installation_id, :source_id)"
                ),
                {
                    "installation_id": str(ids["installation_control"]),
                    "source_id": str(ids["source_control"]),
                },
            )
            connection.execute(
                text("DELETE FROM data_sources WHERE id = :id"),
                {"id": str(ids["source"])},
            )
            connection.execute(
                text("DELETE FROM projects WHERE id = :id"),
                {"id": str(ids["project"])},
            )
            connection.execute(
                text("DELETE FROM clients WHERE id = :id"),
                {"id": str(ids["client"])},
            )



@pytest.mark.parametrize("reservation_state", ["reserved", "unresolved"])
@pytest.mark.parametrize(
    "installation_limit,source_limit",
    [(1, 2), (2, 1)],
)
def test_capacity_exhaustion_with_persistent_reservations(
    engine, reservation_state, installation_limit, source_limit
):
    """Both active reservation states consume each scope's capacity."""
    from uuid import UUID

    from sqlalchemy.orm import Session

    from app.services.data_quality_execution_admission_capacity import (
        require_locked_execution_capacity,
    )

    ids = _phase5e_fixture_ids()
    installation_control_id = str(uuid4())
    source_control_id = str(uuid4())

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

    # All records are isolated to this transaction and rolled back.
    with engine.connect() as connection:
        transaction = connection.begin()

        try:
            insert(
                connection, "clients",
                id=ids["client"],
                name=f"Capacity fixture {ids['client']}",
            )
            insert(
                connection, "projects",
                id=ids["project"],
                client_id=ids["client"],
                name="Disposable capacity project",
            )
            insert(
                connection, "users",
                id=ids["user"],
                username=f"capacity_{ids['user'].replace('-', '')}",
                password_hash="fixture-only-not-a-login",
            )
            insert(
                connection, "data_sources",
                id=ids["source_a"],
                project_id=ids["project"],
                name="Disposable capacity source",
                source_type="postgresql",
                connection_mode="read_only",
            )
            insert(
                connection, "source_objects",
                id=ids["object"],
                data_source_id=ids["source_a"],
                object_type="table",
                object_name="capacity_fixture",
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
                rule_name="Capacity fixture rule",
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
            insert(
                connection, "data_quality_workload_ownership",
                id=ids["ownership"],
                execution_id=ids["execution"],
                project_id=ids["project"],
                rule_id=ids["rule"],
                data_field_id=ids["field"],
                source_object_id=ids["object"],
                data_source_id=ids["source_a"],
                ownership_state=reservation_state,
            )
            insert(
                connection,
                "data_quality_execution_capacity_controls",
                id=installation_control_id,
                scope_type="installation",
                data_source_id=None,
                max_concurrent=installation_limit,
            )
            insert(
                connection,
                "data_quality_execution_capacity_controls",
                id=source_control_id,
                scope_type="source",
                data_source_id=ids["source_a"],
                max_concurrent=source_limit,
            )

            for control_id, scope, reservation_source in (
                (installation_control_id, "installation", None),
                (source_control_id, "source", ids["source_a"]),
            ):
                insert(
                    connection,
                    "data_quality_execution_capacity_reservations",
                    id=str(uuid4()),
                    ownership_id=ids["ownership"],
                    capacity_control_id=control_id,
                    ownership_data_source_id=ids["source_a"],
                    data_source_id=reservation_source,
                    reservation_scope=scope,
                    reservation_state=reservation_state,
                )

            # Assess persisted protection without releasing capacity.
            from types import SimpleNamespace

            from app.services.data_quality_execution_recovery_policy import (
                assess_protected_execution_recovery,
            )

            execution_row = connection.execute(
                text(
                    "SELECT id, status FROM data_quality_rule_executions "
                    "WHERE id = :id"
                ),
                {"id": ids["execution"]},
            ).mappings().one()

            ownership_row = connection.execute(
                text(
                    "SELECT id, execution_id, data_source_id, "
                    "ownership_state, released_at, release_actor, "
                    "release_reason, release_evidence_reference "
                    "FROM data_quality_workload_ownership WHERE id = :id"
                ),
                {"id": ids["ownership"]},
            ).mappings().one()

            reservation_rows = connection.execute(
                text(
                    "SELECT id, ownership_id, ownership_data_source_id, "
                    "data_source_id, capacity_control_id, "
                    "reservation_scope, reservation_state, released_at, "
                    "release_actor, release_reason, "
                    "release_evidence_reference "
                    "FROM data_quality_execution_capacity_reservations "
                    "WHERE ownership_id = :id ORDER BY reservation_scope"
                ),
                {"id": ids["ownership"]},
            ).mappings().all()

            before = (
                dict(execution_row),
                dict(ownership_row),
                [dict(row) for row in reservation_rows],
            )

            result = assess_protected_execution_recovery(
                execution=SimpleNamespace(**before[0]),
                ownership=SimpleNamespace(**before[1]),
                reservations=[
                    SimpleNamespace(**row) for row in before[2]
                ],
                interruption_detected=True,
            )

            assert result == "manual_review_required"
            assert before[1]["ownership_state"] == reservation_state
            assert len(before[2]) == 2
            assert {
                row["reservation_scope"] for row in before[2]
            } == {"installation", "source"}
            assert all(
                row["reservation_state"] == reservation_state
                for row in before[2]
            )

            after = (
                dict(connection.execute(
                    text(
                        "SELECT id, status FROM data_quality_rule_executions "
                        "WHERE id = :id"
                    ),
                    {"id": ids["execution"]},
                ).mappings().one()),
                dict(connection.execute(
                    text(
                        "SELECT id, execution_id, data_source_id, "
                        "ownership_state, released_at, release_actor, "
                        "release_reason, release_evidence_reference "
                        "FROM data_quality_workload_ownership WHERE id = :id"
                    ),
                    {"id": ids["ownership"]},
                ).mappings().one()),
                [
                    dict(row) for row in connection.execute(
                        text(
                            "SELECT id, ownership_id, "
                            "ownership_data_source_id, data_source_id, "
                            "capacity_control_id, reservation_scope, "
                            "reservation_state, released_at, release_actor, "
                            "release_reason, release_evidence_reference "
                            "FROM data_quality_execution_capacity_reservations "
                            "WHERE ownership_id = :id "
                            "ORDER BY reservation_scope"
                        ),
                        {"id": ids["ownership"]},
                    ).mappings().all()
                ],
            )

            assert after == before, (
                "Recovery assessment must not mutate persisted protection."
            )

            # Verify read-only project isolation against persisted
            # PostgreSQL workload ownership records.
            from app.services.data_quality_execution_recovery_inventory import (
                list_project_protected_workload_candidates,
            )

            with Session(bind=connection, autoflush=False) as inventory_db:
                own_records = list_project_protected_workload_candidates(
                    inventory_db,
                    project_id=UUID(ids["project"]),
                )
                other_records = list_project_protected_workload_candidates(
                    inventory_db,
                    project_id=UUID(ids["project_b"]),
                )

                assert len(own_records) == 1
                assert own_records[0].id == UUID(ids["ownership"])
                assert own_records[0].project_id == UUID(ids["project"])
                assert own_records[0].ownership_state == reservation_state
                assert other_records == []

            persisted_state = connection.execute(
                text(
                    "SELECT ownership_state "
                    "FROM data_quality_workload_ownership "
                    "WHERE id = :ownership_id"
                ),
                {"ownership_id": ids["ownership"]},
            ).scalar_one()

            assert persisted_state == reservation_state

            with Session(bind=connection, autoflush=False) as db:
                with pytest.raises(ValueError, match="capacity"):
                    require_locked_execution_capacity(
                        db,
                        data_source_id=UUID(ids["source_a"]),
                        installation_limit=installation_limit,
                    )

            # Released fixture must disappear from recovery inventory.
            # This synthetic state setup tests filtering only; it does
            # not exercise or authorize administrative capacity release.
            audit = {
                "actor": "disposable-test-fixture",
                "reason": "Synthetic released-state inventory test",
                "reference": "phase5e-released-filter-test",
            }

            for table, identity_column, identity in (
                (
                    "data_quality_execution_capacity_reservations",
                    "ownership_id",
                    ids["ownership"],
                ),
                (
                    "data_quality_workload_ownership",
                    "id",
                    ids["ownership"],
                ),
            ):
                state_column = (
                    "reservation_state"
                    if table == "data_quality_execution_capacity_reservations"
                    else "ownership_state"
                )

                connection.execute(
                    text(
                        f"UPDATE {table} "
                        f"SET {state_column} = 'released', "
                        "released_at = now(), "
                        "release_actor = :actor, "
                        "release_reason = :reason, "
                        "release_evidence_reference = :reference "
                        f"WHERE {identity_column} = :identity"
                    ),
                    {**audit, "identity": identity},
                )

            with Session(bind=connection, autoflush=False) as inventory_db:
                released_results = list_project_protected_workload_candidates(
                    inventory_db,
                    project_id=UUID(ids["project"]),
                )

                assert released_results == [], (
                    "Released fixture must disappear from recovery inventory."
                )

            assert connection.execute(
                text(
                    "SELECT count(*) "
                    "FROM data_quality_execution_capacity_reservations "
                    "WHERE ownership_id = :id "
                    "AND reservation_state = 'released'"
                ),
                {"id": ids["ownership"]},
            ).scalar_one() == 2

            assert connection.execute(
                text(
                    "SELECT ownership_state "
                    "FROM data_quality_workload_ownership "
                    "WHERE id = :id"
                ),
                {"id": ids["ownership"]},
            ).scalar_one() == "released"

        finally:
            transaction.rollback()



@pytest.mark.parametrize("failure_mode", ["python", "database_constraint"])
def test_admission_staging_reservation_failure_rolls_back(engine, monkeypatch, failure_mode):
    """A reservation-stage failure must leave no partial admission records."""
    from types import SimpleNamespace
    from uuid import UUID

    from sqlalchemy.orm import Session

    # Register referenced ORM tables before flushing execution records.
    # The existing integration fixture otherwise uses Core SQL inserts.
    from app.models import data_quality_rule
    from app.models import data_quality_rule_version
    from app.models import data_quality_rule_execution
    from app.models import data_quality_workload_ownership
    from app.models import data_quality_execution_capacity_control
    from app.models import data_quality_execution_capacity_reservation

    from app.services import data_quality_execution_admission_staging as staging

    ids = _phase5e_fixture_ids()
    installation_id = str(uuid4())
    source_control_id = str(uuid4())

    def insert(connection, table, **values):
        columns = ", ".join(values)
        placeholders = ", ".join(f":{column}" for column in values)
        connection.execute(
            text(
                f"INSERT INTO {table} ({columns}) "
                f"VALUES ({placeholders})"
            ),
            values,
        )

    with engine.connect() as connection:
        outer = connection.begin()
        try:
            insert(
                connection, "clients",
                id=ids["client"],
                name=f"Admission rollback fixture {ids['client']}",
            )
            insert(
                connection, "projects",
                id=ids["project"],
                client_id=ids["client"],
                name="Disposable admission rollback project",
            )
            insert(
                connection, "users",
                id=ids["user"],
                username=f"rollback_{ids['user'].replace('-', '')}",
                password_hash="fixture-only-not-a-login",
            )
            insert(
                connection, "data_sources",
                id=ids["source_a"],
                project_id=ids["project"],
                name="Disposable admission rollback source",
                source_type="postgresql",
                connection_mode="read_only",
            )
            insert(
                connection, "source_objects",
                id=ids["object"],
                data_source_id=ids["source_a"],
                object_type="table",
                object_name="rollback_fixture",
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
                rule_name="Rollback fixture rule",
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
                connection, "data_quality_execution_capacity_controls",
                id=installation_id,
                scope_type="installation",
                data_source_id=None,
                max_concurrent=2,
            )
            insert(
                connection, "data_quality_execution_capacity_controls",
                id=source_control_id,
                scope_type="source",
                data_source_id=ids["source_a"],
                max_concurrent=1,
            )

            prepared = {
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
                    data_source_id=UUID(ids["source_a"]),
                ),
                "source": SimpleNamespace(
                    id=UUID(ids["source_a"]),
                    project_id=UUID(ids["project"]),
                ),
            }

            real_add = Session.add

            def fail_on_source_reservation(self, instance, *args, **kwargs):
                if (
                    instance.__class__.__name__
                    == "DataQualityExecutionCapacityReservation"
                    and instance.reservation_scope == "source"
                ):
                    if failure_mode == "python":
                        raise RuntimeError(
                            "synthetic source reservation failure"
                        )

                    # Force a real PostgreSQL foreign-key violation.
                    instance.capacity_control_id = uuid4()

                return real_add(self, instance, *args, **kwargs)

            with monkeypatch.context() as patch:
                patch.setattr(Session, "add", fail_on_source_reservation)

                with Session(bind=connection, autoflush=False) as db:
                    if failure_mode == "python":
                        expected_error = RuntimeError
                    else:
                        expected_error = IntegrityError

                    with pytest.raises(expected_error) as error:
                        with db.begin_nested():
                            staging.stage_protected_execution_records(
                                db,
                                prepared=prepared,
                                project_id=UUID(ids["project"]),
                                actor_user_id=UUID(ids["user"]),
                                installation_limit=2,
                            )

                    if failure_mode == "database_constraint":
                        assert error.value.orig.sqlstate == "23503"
                    else:
                        assert (
                            "synthetic source reservation failure"
                            in str(error.value)
                        )

            for table, key in (
                ("data_quality_rule_executions", "project_id"),
                ("data_quality_workload_ownership", "project_id"),
                ("data_quality_execution_capacity_reservations",
                 "ownership_data_source_id"),
            ):
                value = (
                    ids["source_a"]
                    if key == "ownership_data_source_id"
                    else ids["project"]
                )
                count = connection.execute(
                    text(
                        f"SELECT count(*) FROM {table} "
                        f"WHERE {key} = :value"
                    ),
                    {"value": value},
                ).scalar_one()

                assert count == 0, (
                    f"Partial admission records remained in {table}"
                )
        finally:
            outer.rollback()



def _cleanup_coordinator_disposable_fixture(
    engine, *, ids, installation_id, source_control_id, execution_grant_id
):
    """Remove only synthetic coordinator fixture records."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "DELETE FROM data_quality_execution_capacity_reservations "
                "WHERE ownership_data_source_id = :source_id"
            ),
            {"source_id": ids["source_a"]},
        )
        connection.execute(
            text(
                "DELETE FROM data_quality_workload_ownership "
                "WHERE data_source_id = :source_id"
            ),
            {"source_id": ids["source_a"]},
        )
        connection.execute(
            text(
                "DELETE FROM data_quality_rule_executions "
                "WHERE project_id = :project_id"
            ),
            {"project_id": ids["project"]},
        )
        connection.execute(
            text(
                "DELETE FROM data_quality_execution_capacity_controls "
                "WHERE id IN (:installation_id, :source_control_id)"
            ),
            {
                "installation_id": installation_id,
                "source_control_id": source_control_id,
            },
        )
        connection.execute(
            text(
                "DELETE FROM data_quality_rule_versions "
                "WHERE id = :id"
            ),
            {"id": ids["version"]},
        )
        connection.execute(
            text("DELETE FROM data_quality_rules WHERE id = :id"),
            {"id": ids["rule"]},
        )
        connection.execute(
            text("DELETE FROM data_fields WHERE id = :id"),
            {"id": ids["field"]},
        )
        connection.execute(
            text("DELETE FROM source_objects WHERE id = :id"),
            {"id": ids["object"]},
        )
        connection.execute(
            text("DELETE FROM data_sources WHERE id = :id"),
            {"id": ids["source_a"]},
        )
        connection.execute(
            text("DELETE FROM project_access WHERE id = :id"),
            {"id": execution_grant_id},
        )
        connection.execute(
            text("DELETE FROM users WHERE id = :id"),
            {"id": ids["user"]},
        )
        connection.execute(
            text("DELETE FROM projects WHERE id = :id"),
            {"id": ids["project"]},
        )
        connection.execute(
            text("DELETE FROM clients WHERE id = :id"),
            {"id": ids["client"]},
        )


def _create_coordinator_disposable_fixture(engine):
    """Create synthetic coordinator records in disposable PostgreSQL."""
    from types import SimpleNamespace
    from uuid import UUID

    ids = _phase5e_fixture_ids()
    installation_id = str(uuid4())
    source_control_id = str(uuid4())
    execution_grant_id = str(uuid4())

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

    # Commit only synthetic fixture metadata to the disposable database.
    with engine.begin() as connection:
        insert(
            connection, "clients",
            id=ids["client"],
            name=f"Concurrent admission fixture {ids['client']}",
        )
        insert(
            connection, "projects",
            id=ids["project"],
            client_id=ids["client"],
            name="Disposable concurrency project",
        )
        insert(
            connection, "users",
            id=ids["user"],
            username=f"concurrency_{ids['user'].replace('-', '')}",
            password_hash="fixture-only-not-a-login",
        )
        insert(
            connection, "project_access",
            id=execution_grant_id,
            user_id=ids["user"],
            project_id=ids["project"],
            can_execute_dq_rules=True,
        )
        insert(
            connection, "data_sources",
            id=ids["source_a"],
            project_id=ids["project"],
            name="Disposable concurrency source",
            source_type="postgresql",
            connection_mode="read_only",
        )
        insert(
            connection, "source_objects",
            id=ids["object"],
            data_source_id=ids["source_a"],
            object_type="table",
            object_name="concurrent_fixture",
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
            rule_name="Concurrency fixture rule",
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
            connection, "data_quality_execution_capacity_controls",
            id=installation_id,
            scope_type="installation",
            data_source_id=None,
            max_concurrent=1,
        )
        insert(
            connection, "data_quality_execution_capacity_controls",
            id=source_control_id,
            scope_type="source",
            data_source_id=ids["source_a"],
            max_concurrent=1,
        )

    prepared = {
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
            data_source_id=UUID(ids["source_a"]),
        ),
        "source": SimpleNamespace(
            id=UUID(ids["source_a"]),
            project_id=UUID(ids["project"]),
        ),
    }

    return (
        ids,
        installation_id,
        source_control_id,
        execution_grant_id,
        prepared,
    )


def test_competing_admission_cannot_exceed_committed_capacity(engine):
    """A competing admission must wait for locks and see committed capacity."""
    from types import SimpleNamespace
    from uuid import UUID

    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session

    # Register the ORM dependency graph before flushing.
    from app.models import data_quality_rule
    from app.models import data_quality_rule_version
    from app.models import data_quality_rule_execution
    from app.models import data_quality_workload_ownership
    from app.models import data_quality_execution_capacity_control
    from app.models import data_quality_execution_capacity_reservation

    from app.services.data_quality_execution_admission_capacity import (
        require_locked_execution_capacity,
    )
    from app.services.data_quality_execution_admission_staging import (
        stage_protected_execution_records,
    )

    (
        ids,
        installation_id,
        source_control_id,
        execution_grant_id,
        prepared,
    ) = _create_coordinator_disposable_fixture(engine)

    try:
        with Session(engine, autoflush=False) as first:
            staged = stage_protected_execution_records(
                first,
                prepared=prepared,
                project_id=UUID(ids["project"]),
                actor_user_id=UUID(ids["user"]),
                installation_limit=1,
            )

            assert staged["execution"].status == "pending"
            # Retain identity before commit expires ORM attributes.
            committed_execution_id = staged["execution"].id

            # Cross-transaction admission visibility boundary:
            # flushed records must not be visible before commit.
            with engine.connect() as observer:
                observer.execute(
                    text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                )
                precommit_counts = {
                    "execution": observer.execute(
                        text(
                            "SELECT count(*) FROM data_quality_rule_executions "
                            "WHERE project_id = :project_id"
                        ),
                        {"project_id": ids["project"]},
                    ).scalar_one(),
                    "ownership": observer.execute(
                        text(
                            "SELECT count(*) FROM data_quality_workload_ownership "
                            "WHERE data_source_id = :source_id"
                        ),
                        {"source_id": ids["source_a"]},
                    ).scalar_one(),
                    "reservations": observer.execute(
                        text(
                            "SELECT count(*) "
                            "FROM data_quality_execution_capacity_reservations "
                            "WHERE ownership_data_source_id = :source_id"
                        ),
                        {"source_id": ids["source_a"]},
                    ).scalar_one(),
                }

                assert precommit_counts == {
                    "execution": 0,
                    "ownership": 0,
                    "reservations": 0,
                }, "Uncommitted admission must not be visible."

            # Snapshot visibility from independent PostgreSQL sessions.
            from app.services.data_quality_execution_coordinator_protection_snapshot import (
                inspect_protected_execution_snapshot,
            )

            with Session(engine, autoflush=False) as snapshot_session:
                with pytest.raises(ValueError, match="not found"):
                    inspect_protected_execution_snapshot(
                        snapshot_session,
                        project_id=UUID(ids["project"]),
                        execution_id=committed_execution_id,
                        expected_status="pending",
                    )

            # Independent committed-protection verifier integration checks.
            from app.services.data_quality_execution_coordinator_committed_snapshot import (
                verify_committed_protection,
            )

            with pytest.raises(ValueError, match="not found"):
                verify_committed_protection(
                    session_factory=lambda: Session(
                        engine, autoflush=False
                    ),
                    project_id=UUID(ids["project"]),
                    execution_id=committed_execution_id,
                    expected_status="pending",
                )

            # Run the competing admission in another thread while
            # the first transaction still holds its capacity locks.
            from concurrent.futures import ThreadPoolExecutor

            def competing_admission():
                with Session(engine, autoflush=False) as competing:
                    try:
                        with competing.begin():
                            competing.execute(
                                text("SET LOCAL lock_timeout = '300ms'")
                            )
                            require_locked_execution_capacity(
                                competing,
                                data_source_id=UUID(ids["source_a"]),
                                installation_limit=1,
                            )
                    except OperationalError as error:
                        return getattr(error.orig, "sqlstate", None)

                return "unexpectedly_admitted"

            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(competing_admission)
                result = future.result(timeout=10)

            assert result == "55P03", (
                "Competing thread must not acquire capacity locks "
                f"while the first transaction is active: {result}"
            )

            # Capacity and both reservations become visible together.
            first.commit()

        # A fresh connection must see all committed protection records.
        with engine.connect() as observer:
            postcommit_counts = {
                "execution": observer.execute(
                    text(
                        "SELECT count(*) FROM data_quality_rule_executions "
                        "WHERE project_id = :project_id AND status = 'pending'"
                    ),
                    {"project_id": ids["project"]},
                ).scalar_one(),
                "ownership": observer.execute(
                    text(
                        "SELECT count(*) FROM data_quality_workload_ownership "
                        "WHERE data_source_id = :source_id "
                        "AND ownership_state = 'reserved'"
                    ),
                    {"source_id": ids["source_a"]},
                ).scalar_one(),
                "reservations": observer.execute(
                    text(
                        "SELECT count(*) "
                        "FROM data_quality_execution_capacity_reservations "
                        "WHERE ownership_data_source_id = :source_id "
                        "AND reservation_state = 'reserved'"
                    ),
                    {"source_id": ids["source_a"]},
                ).scalar_one(),
            }

            assert postcommit_counts == {
                "execution": 1,
                "ownership": 1,
                "reservations": 2,
            }, "All protection records must become visible after commit."

        # A new session must observe committed admission protection.
        with Session(engine, autoflush=False) as snapshot_session:
            pending_snapshot = inspect_protected_execution_snapshot(
                snapshot_session,
                project_id=UUID(ids["project"]),
                execution_id=committed_execution_id,
                expected_status="pending",
            )
            assert pending_snapshot.id == committed_execution_id
            assert pending_snapshot.status == "pending"

        # Verify committed admission using a separately owned session.
        verified_pending_id = verify_committed_protection(
            session_factory=lambda: Session(engine, autoflush=False),
            project_id=UUID(ids["project"]),
            execution_id=committed_execution_id,
            expected_status="pending",
        )
        assert verified_pending_id == committed_execution_id

        # The competing admission must now observe exhausted capacity.
        with Session(engine, autoflush=False) as competing:
            with pytest.raises(ValueError, match="capacity"):
                require_locked_execution_capacity(
                    competing,
                    data_source_id=UUID(ids["source_a"]),
                    installation_limit=1,
                )
            competing.rollback()

        with engine.connect() as connection:
            counts = connection.execute(
                text(
                    "SELECT reservation_scope, count(*) "
                    "FROM data_quality_execution_capacity_reservations "
                    "WHERE ownership_data_source_id = :source_id "
                    "GROUP BY reservation_scope"
                ),
                {"source_id": ids["source_a"]},
            ).all()

            assert dict(counts) == {
                "installation": 1,
                "source": 1,
            }

            assert connection.execute(
                text(
                    "SELECT count(*) FROM data_quality_workload_ownership "
                    "WHERE data_source_id = :source_id "
                    "AND ownership_state = 'reserved'"
                ),
                {"source_id": ids["source_a"]},
            ).scalar_one() == 1

        # Protected start from a fresh committed-admission session.
        # No worker or source measurement is launched.
        from datetime import datetime, timezone
        from app.services.data_quality_execution_protected_start import (
            stage_protected_running_execution,
        )

        with Session(engine, autoflush=False) as starter:
            with starter.begin():
                started = stage_protected_running_execution(
                    starter,
                    project_id=UUID(ids["project"]),
                    execution_id=committed_execution_id,
                    actor_user_id=UUID(ids["user"]),
                    started_at=datetime.now(timezone.utc),
                )
                assert started.status == "running"

        # The committed RUNNING transition must also be visible,
        # with the same reserved workload protection intact.
        with Session(engine, autoflush=False) as snapshot_session:
            running_snapshot = inspect_protected_execution_snapshot(
                snapshot_session,
                project_id=UUID(ids["project"]),
                execution_id=committed_execution_id,
                expected_status="running",
            )
            assert running_snapshot.id == committed_execution_id
            assert running_snapshot.status == "running"

        # Verify committed RUNNING protection through another new session.
        verified_running_id = verify_committed_protection(
            session_factory=lambda: Session(engine, autoflush=False),
            project_id=UUID(ids["project"]),
            execution_id=committed_execution_id,
            expected_status="running",
        )
        assert verified_running_id == committed_execution_id

        # A separate connection must see the committed transition,
        # while workload ownership and reservations remain protected.
        with engine.connect() as observer:
            assert observer.execute(
                text(
                    "SELECT status FROM data_quality_rule_executions "
                    "WHERE id = :execution_id"
                ),
                {"execution_id": str(committed_execution_id)},
            ).scalar_one() == "running"

            assert observer.execute(
                text(
                    "SELECT ownership_state FROM data_quality_workload_ownership "
                    "WHERE execution_id = :execution_id"
                ),
                {"execution_id": str(committed_execution_id)},
            ).scalar_one() == "reserved"

            assert observer.execute(
                text(
                    "SELECT count(*) "
                    "FROM data_quality_execution_capacity_reservations "
                    "WHERE ownership_data_source_id = :source_id "
                    "AND reservation_state = 'reserved'"
                ),
                {"source_id": ids["source_a"]},
            ).scalar_one() == 2

    finally:
        _cleanup_coordinator_disposable_fixture(
            engine,
            ids=ids,
            installation_id=installation_id,
            source_control_id=source_control_id,
            execution_grant_id=execution_grant_id,
        )


def test_coordinator_commits_and_verifies_protected_admission(engine):
    """Coordinator admission must commit before independent verification."""
    from types import SimpleNamespace
    from uuid import UUID

    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session

    # Register the ORM dependency graph before flushing.
    from app.models import data_quality_rule
    from app.models import data_quality_rule_version
    from app.models import data_quality_rule_execution
    from app.models import data_quality_workload_ownership
    from app.models import data_quality_execution_capacity_control
    from app.models import data_quality_execution_capacity_reservation

    from app.services.data_quality_execution_admission_capacity import (
        require_locked_execution_capacity,
    )
    from app.services.data_quality_execution_admission_staging import (
        stage_protected_execution_records,
    )

    (
        ids,
        installation_id,
        source_control_id,
        execution_grant_id,
        prepared,
    ) = _create_coordinator_disposable_fixture(engine)

    try:
        from app.services.data_quality_execution_coordinator_admission import (
            commit_and_verify_protected_admission,
        )

        # The staging callback returns a UUID while its ORM session
        # is still open. The coordinator owns commit and verification.
        def stage_admission(db):
            staged = stage_protected_execution_records(
                db,
                prepared=prepared,
                project_id=UUID(ids["project"]),
                actor_user_id=UUID(ids["user"]),
                installation_limit=1,
            )
            assert staged["execution"].status == "pending"
            return staged["execution"].id

        execution_id = commit_and_verify_protected_admission(
            session_factory=lambda: Session(engine, autoflush=False),
            project_id=UUID(ids["project"]),
            stage_admission=stage_admission,
        )

        assert isinstance(execution_id, UUID)

        # The coordinator has returned, so this connection observes
        # only independently committed database state.
        with engine.connect() as observer:
            execution_count = observer.execute(
                text(
                    "SELECT count(*) FROM data_quality_rule_executions "
                    "WHERE id = :execution_id "
                    "AND project_id = :project_id "
                    "AND status = 'pending'"
                ),
                {
                    "execution_id": str(execution_id),
                    "project_id": ids["project"],
                },
            ).scalar_one()

            ownership_count = observer.execute(
                text(
                    "SELECT count(*) FROM data_quality_workload_ownership "
                    "WHERE execution_id = :execution_id "
                    "AND ownership_state = 'reserved'"
                ),
                {"execution_id": str(execution_id)},
            ).scalar_one()

            reservation_count = observer.execute(
                text(
                    "SELECT count(*) "
                    "FROM data_quality_execution_capacity_reservations "
                    "WHERE ownership_data_source_id = :source_id "
                    "AND reservation_state = 'reserved'"
                ),
                {"source_id": ids["source_a"]},
            ).scalar_one()

        assert execution_count == 1
        assert ownership_count == 1
        assert reservation_count == 2

    finally:
        _cleanup_coordinator_disposable_fixture(
            engine,
            ids=ids,
            installation_id=installation_id,
            source_control_id=source_control_id,
            execution_grant_id=execution_grant_id,
        )


def test_coordinator_commits_and_verifies_protected_start(engine):
    """Admission and protected start must commit in separate transactions."""
    from types import SimpleNamespace
    from uuid import UUID

    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session

    # Register the ORM dependency graph before flushing.
    from app.models import data_quality_rule
    from app.models import data_quality_rule_version
    from app.models import data_quality_rule_execution
    from app.models import data_quality_workload_ownership
    from app.models import data_quality_execution_capacity_control
    from app.models import data_quality_execution_capacity_reservation

    from app.services.data_quality_execution_admission_capacity import (
        require_locked_execution_capacity,
    )
    from app.services.data_quality_execution_admission_staging import (
        stage_protected_execution_records,
    )

    (
        ids,
        installation_id,
        source_control_id,
        execution_grant_id,
        prepared,
    ) = _create_coordinator_disposable_fixture(engine)

    try:
        from datetime import datetime, timezone

        from app.services.data_quality_execution_coordinator_admission import (
            commit_and_verify_protected_admission,
        )
        from app.services.data_quality_execution_coordinator_start import (
            commit_and_verify_protected_start,
        )
        from app.services.data_quality_execution_protected_start import (
            stage_protected_running_execution,
        )

        session_factory = lambda: Session(engine, autoflush=False)

        def stage_admission(db):
            staged = stage_protected_execution_records(
                db,
                prepared=prepared,
                project_id=UUID(ids["project"]),
                actor_user_id=UUID(ids["user"]),
                installation_limit=1,
            )
            assert staged["execution"].status == "pending"
            return staged["execution"].id

        execution_id = commit_and_verify_protected_admission(
            session_factory=session_factory,
            project_id=UUID(ids["project"]),
            stage_admission=stage_admission,
        )

        assert isinstance(execution_id, UUID)

        def stage_start(db):
            started = stage_protected_running_execution(
                db,
                project_id=UUID(ids["project"]),
                execution_id=execution_id,
                actor_user_id=UUID(ids["user"]),
                started_at=datetime.now(timezone.utc),
            )
            assert started.status == "running"
            return started.id

        started_id = commit_and_verify_protected_start(
            session_factory=session_factory,
            project_id=UUID(ids["project"]),
            execution_id=execution_id,
            stage_start=stage_start,
        )

        assert started_id == execution_id

        # Verify independently committed records, not session-local state.
        with engine.connect() as observer:
            status = observer.execute(
                text(
                    "SELECT status FROM data_quality_rule_executions "
                    "WHERE id = :execution_id "
                    "AND project_id = :project_id"
                ),
                {
                    "execution_id": str(execution_id),
                    "project_id": ids["project"],
                },
            ).scalar_one()

            ownership_state = observer.execute(
                text(
                    "SELECT ownership_state "
                    "FROM data_quality_workload_ownership "
                    "WHERE execution_id = :execution_id"
                ),
                {"execution_id": str(execution_id)},
            ).scalar_one()

            reservation_count = observer.execute(
                text(
                    "SELECT count(*) "
                    "FROM data_quality_execution_capacity_reservations "
                    "WHERE ownership_data_source_id = :source_id "
                    "AND reservation_state = 'reserved'"
                ),
                {"source_id": ids["source_a"]},
            ).scalar_one()

        assert status == "running"
        assert ownership_state == "reserved"
        assert reservation_count == 2

    finally:
        _cleanup_coordinator_disposable_fixture(
            engine,
            ids=ids,
            installation_id=installation_id,
            source_control_id=source_control_id,
            execution_grant_id=execution_grant_id,
        )


def test_combined_coordinator_commits_and_verifies_both_stages(engine):
    """Combined coordinator commits and verifies both protected stages."""
    from types import SimpleNamespace
    from uuid import UUID

    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session

    # Register the ORM dependency graph before flushing.
    from app.models import data_quality_rule
    from app.models import data_quality_rule_version
    from app.models import data_quality_rule_execution
    from app.models import data_quality_workload_ownership
    from app.models import data_quality_execution_capacity_control
    from app.models import data_quality_execution_capacity_reservation

    from app.services.data_quality_execution_admission_capacity import (
        require_locked_execution_capacity,
    )
    from app.services.data_quality_execution_admission_staging import (
        stage_protected_execution_records,
    )

    (
        ids,
        installation_id,
        source_control_id,
        execution_grant_id,
        prepared,
    ) = _create_coordinator_disposable_fixture(engine)

    try:
        from datetime import datetime, timezone

        from app.services.data_quality_execution_coordinator_sequence import (
            coordinate_protected_admission_and_start,
        )
        from app.services.data_quality_execution_protected_start import (
            stage_protected_running_execution,
        )

        session_factory = lambda: Session(engine, autoflush=False)

        def stage_admission(db):
            staged = stage_protected_execution_records(
                db,
                prepared=prepared,
                project_id=UUID(ids["project"]),
                actor_user_id=UUID(ids["user"]),
                installation_limit=1,
            )
            assert staged["execution"].status == "pending"
            return staged["execution"].id

        # The start callback must be created only after the
        # admission coordinator has committed and verified PENDING.
        start_factory_calls = []

        def stage_start_factory(execution_id):
            assert isinstance(execution_id, UUID)
            start_factory_calls.append(execution_id)

            def stage_start(db):
                started = stage_protected_running_execution(
                    db,
                    project_id=UUID(ids["project"]),
                    execution_id=execution_id,
                    actor_user_id=UUID(ids["user"]),
                    started_at=datetime.now(timezone.utc),
                )
                assert started.status == "running"
                return started.id

            return stage_start

        execution_id = coordinate_protected_admission_and_start(
            session_factory=session_factory,
            project_id=UUID(ids["project"]),
            stage_admission=stage_admission,
            stage_start_factory=stage_start_factory,
        )

        assert isinstance(execution_id, UUID)
        assert start_factory_calls == [execution_id]

        # Observe committed state in a separate PostgreSQL connection.
        with engine.connect() as observer:
            execution_rows = observer.execute(
                text(
                    "SELECT status FROM data_quality_rule_executions "
                    "WHERE id = :execution_id "
                    "AND project_id = :project_id"
                ),
                {
                    "execution_id": str(execution_id),
                    "project_id": ids["project"],
                },
            ).all()

            ownership_rows = observer.execute(
                text(
                    "SELECT ownership_state "
                    "FROM data_quality_workload_ownership "
                    "WHERE execution_id = :execution_id"
                ),
                {"execution_id": str(execution_id)},
            ).all()

            reservations = observer.execute(
                text(
                    "SELECT reservation_state "
                    "FROM data_quality_execution_capacity_reservations "
                    "WHERE ownership_data_source_id = :source_id"
                ),
                {"source_id": ids["source_a"]},
            ).all()

        assert execution_rows == [("running",)]
        assert ownership_rows == [("reserved",)]
        assert len(reservations) == 2
        assert all(row[0] == "reserved" for row in reservations)

        # Repeated protected start must fail before staging another
        # transition. The execution is already committed as RUNNING.
        from app.services.data_quality_execution_coordinator_start import (
            commit_and_verify_protected_start,
        )

        start_stage_called = []

        def forbidden_second_start(db):
            start_stage_called.append(True)
            raise AssertionError(
                "A second RUNNING transition must not be staged."
            )

        with pytest.raises(ValueError, match="status"):
            commit_and_verify_protected_start(
                session_factory=session_factory,
                project_id=UUID(ids["project"]),
                execution_id=execution_id,
                stage_start=forbidden_second_start,
            )

        assert start_stage_called == []

        # A fresh database connection confirms the failed attempt
        # left the committed execution and reservations unchanged.
        with engine.connect() as observer:
            assert observer.execute(
                text(
                    "SELECT status FROM data_quality_rule_executions "
                    "WHERE id = :execution_id"
                ),
                {"execution_id": str(execution_id)},
            ).scalar_one() == "running"

            assert observer.execute(
                text(
                    "SELECT ownership_state "
                    "FROM data_quality_workload_ownership "
                    "WHERE execution_id = :execution_id"
                ),
                {"execution_id": str(execution_id)},
            ).scalar_one() == "reserved"

            assert observer.execute(
                text(
                    "SELECT count(*) "
                    "FROM data_quality_execution_capacity_reservations "
                    "WHERE ownership_data_source_id = :source_id "
                    "AND reservation_state = 'reserved'"
                ),
                {"source_id": ids["source_a"]},
            ).scalar_one() == 2


    finally:
        _cleanup_coordinator_disposable_fixture(
            engine,
            ids=ids,
            installation_id=installation_id,
            source_control_id=source_control_id,
            execution_grant_id=execution_grant_id,
        )
