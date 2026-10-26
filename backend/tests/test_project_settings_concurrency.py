"""Integration test for PostgreSQL project-setting row locks."""

import os
import uuid

import psycopg
import pytest


@pytest.mark.integration
def test_project_settings_row_lock_blocks_concurrent_update():
    """A second transaction cannot lock a project held by another transaction."""
    database_url = os.environ.get("GEOVARIS_LOCK_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Isolated PostgreSQL test connection not configured.")

    client_id = uuid.uuid4()
    project_id = uuid.uuid4()

    with psycopg.connect(database_url, autocommit=True) as setup:
        try:
            setup.execute(
                "INSERT INTO clients (id, name) VALUES (%s, %s)",
                (client_id, f"Synthetic lock test {client_id}"),
            )
            setup.execute(
                "INSERT INTO projects (id, client_id, name) VALUES (%s, %s, %s)",
                (project_id, client_id, "Synthetic locking test project"),
            )

            with (
                psycopg.connect(database_url) as first,
                psycopg.connect(database_url) as second,
            ):
                first.execute(
                    "SELECT id FROM projects WHERE id = %s FOR UPDATE",
                    (project_id,),
                ).fetchone()

                second.execute("SET LOCAL lock_timeout = '500ms'")

                with pytest.raises(psycopg.errors.LockNotAvailable):
                    second.execute(
                        "SELECT id FROM projects WHERE id = %s FOR UPDATE",
                        (project_id,),
                    ).fetchone()

                second.rollback()
                first.rollback()

            with psycopg.connect(database_url) as verification:
                row = verification.execute(
                    "SELECT allow_steward_self_approval "
                    "FROM projects WHERE id = %s",
                    (project_id,),
                ).fetchone()

                assert row == (False,)
        finally:
            setup.execute(
                "DELETE FROM projects WHERE id = %s",
                (project_id,),
            )
            setup.execute(
                "DELETE FROM clients WHERE id = %s",
                (client_id,),
            )
