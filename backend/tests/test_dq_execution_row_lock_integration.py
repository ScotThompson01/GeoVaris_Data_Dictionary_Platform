"""Phase 5E PostgreSQL execution row-lock integration test.

Runs only with explicit opt-in against the isolated migration-test database.
Creates synthetic fixtures and removes them after testing.
"""

import os
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.services.data_quality_execution_persistence import (
    get_authorized_locked_execution,
)


@pytest.mark.integration
def test_execution_row_lock_prevents_concurrent_start():
    if os.environ.get("GEOVARIS_PHASE5E_LOCK_TEST") != "1":
        pytest.skip("Phase 5E execution locking test not enabled.")

    from scripts.phase5e_migration_preflight import main as verify_database

    verify_database()

    ids = {
        name: uuid.uuid4()
        for name in (
            "client", "project", "user", "source",
            "object", "field", "rule", "version", "execution"
        )
    }

    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    fixtures_committed = False

    try:
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            assert revision == "0024", "Phase 5E migration 0024 is required."

        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO clients (id, name) VALUES (:id, :name)"),
                {"id": ids["client"], "name": "Synthetic Phase 5E lock client"},
            )
            connection.execute(
                text(
                    "INSERT INTO projects (id, client_id, name) "
                    "VALUES (:id, :client_id, :name)"
                ),
                {
                    "id": ids["project"],
                    "client_id": ids["client"],
                    "name": "Synthetic Phase 5E lock project",
                },
            )
            connection.execute(
                text(
                    "INSERT INTO users (id, username, password_hash) "
                    "VALUES (:id, :username, :password_hash)"
                ),
                {
                    "id": ids["user"],
                    "username": f"phase5e_lock_{ids['user'].hex}",
                    "password_hash": "synthetic-test-only-placeholder",
                },
            )
            connection.execute(
                text(
                    "INSERT INTO data_sources "
                    "(id, project_id, name, source_type, connection_mode) "
                    "VALUES (:id, :project_id, :name, :source_type, :mode)"
                ),
                {
                    "id": ids["source"],
                    "project_id": ids["project"],
                    "name": "Synthetic disconnected test source",
                    "source_type": "postgresql",
                    "mode": "read_only",
                },
            )
            connection.execute(
                text(
                    "INSERT INTO source_objects "
                    "(id, data_source_id, object_type, object_name) "
                    "VALUES (:id, :source_id, 'table', 'synthetic_lock_object')"
                ),
                {"id": ids["object"], "source_id": ids["source"]},
            )
            connection.execute(
                text(
                    "INSERT INTO data_fields "
                    "(id, source_object_id, field_name, ordinal_position) "
                    "VALUES (:id, :object_id, 'test_value', 1)"
                ),
                {"id": ids["field"], "object_id": ids["object"]},
            )
            connection.execute(
                text(
                    "INSERT INTO data_quality_rules "
                    "(id, data_field_id, rule_name, status) "
                    "VALUES (:id, :field_id, 'Synthetic lock rule', 'draft')"
                ),
                {"id": ids["rule"], "field_id": ids["field"]},
            )
            connection.execute(
                text(
                    "INSERT INTO data_quality_rule_versions "
                    "(id, rule_id, version_number, min_value, max_value) "
                    "VALUES (:id, :rule_id, 1, 0, 100)"
                ),
                {"id": ids["version"], "rule_id": ids["rule"]},
            )
            connection.execute(
                text(
                    "INSERT INTO data_quality_rule_executions "
                    "(id, project_id, actor_user_id, rule_id, version_id, status) "
                    "VALUES (:id, :project_id, :user_id, :rule_id, "
                    ":version_id, 'pending')"
                ),
                {
                    "id": ids["execution"],
                    "project_id": ids["project"],
                    "user_id": ids["user"],
                    "rule_id": ids["rule"],
                    "version_id": ids["version"],
                },
            )

        fixtures_committed = True

        # Authorization behavior is covered by separate unit tests.
        # Here we exercise the actual PostgreSQL locking query.
        with patch(
            "app.services.project_authorization.require_dq_rule_executor"
        ):
            with Session(engine) as first, Session(engine) as second:
                try:
                    locked = get_authorized_locked_execution(
                        first,
                        project_id=ids["project"],
                        execution_id=ids["execution"],
                        actor_user_id=ids["user"],
                    )
                    assert locked.status == "pending"

                    second.execute(
                        text("SET LOCAL lock_timeout = '500ms'")
                    )

                    with pytest.raises(OperationalError) as exc:
                        get_authorized_locked_execution(
                            second,
                            project_id=ids["project"],
                            execution_id=ids["execution"],
                            actor_user_id=ids["user"],
                        )

                    assert getattr(exc.value.orig, "sqlstate", None) == "55P03"

                finally:
                    second.rollback()
                    first.rollback()

        # Simulate an execution cached before another worker cancels it.
        from datetime import datetime, timezone
        from sqlalchemy import select
        from app.models.data_quality_rule_execution import DataQualityRuleExecution
        from app.services.data_quality_execution_persistence import (
            stage_running_execution,
        )

        with patch(
            "app.services.project_authorization.require_dq_rule_executor"
        ):
            with Session(engine) as cached_session, Session(engine) as changing_session:
                try:
                    cached = cached_session.scalar(
                        select(DataQualityRuleExecution).where(
                            DataQualityRuleExecution.id == ids["execution"]
                        )
                    )
                    assert cached is not None
                    assert cached.status == "pending"

                    changing_session.execute(
                        text(
                            "UPDATE data_quality_rule_executions "
                            "SET status = 'cancelled' WHERE id = :id"
                        ),
                        {"id": ids["execution"]},
                    )
                    changing_session.commit()

                    # The first session still holds the outdated object.
                    assert cached.status == "pending"

                    locked = get_authorized_locked_execution(
                        cached_session,
                        project_id=ids["project"],
                        execution_id=ids["execution"],
                        actor_user_id=ids["user"],
                    )

                    assert locked is cached
                    assert locked.status == "cancelled"

                    with pytest.raises(ValueError, match="not permitted"):
                        stage_running_execution(
                            cached_session,
                            execution=locked,
                            started_at=datetime.now(timezone.utc),
                        )
                finally:
                    changing_session.rollback()
                    cached_session.rollback()

        with engine.connect() as connection:
            status = connection.execute(
                text(
                    "SELECT status FROM data_quality_rule_executions "
                    "WHERE id = :id"
                ),
                {"id": ids["execution"]},
            ).scalar_one()
            assert status == "cancelled"

    finally:
        try:
            if fixtures_committed:
                with engine.begin() as connection:
                    for table_name, key in (
                        ("data_quality_rule_executions", "execution"),
                        ("data_quality_rule_versions", "version"),
                        ("data_quality_rules", "rule"),
                        ("data_fields", "field"),
                        ("source_objects", "object"),
                        ("data_sources", "source"),
                        ("projects", "project"),
                        ("users", "user"),
                        ("clients", "client"),
                    ):
                        connection.execute(
                            text(f"DELETE FROM {table_name} WHERE id = :id"),
                            {"id": ids[key]},
                        )
        finally:
            engine.dispose()
