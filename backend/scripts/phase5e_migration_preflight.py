"""Safety preflight for the isolated Phase 5E migration test database.

This script verifies the target database. It never executes migrations.
"""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


EXPECTED_HOST = "migration_test_db"
EXPECTED_PORT = 5432
EXPECTED_DATABASE = "geovaris_phase5e_migration_test"
EXPECTED_USER = "geovaris_migration_test"


def main() -> None:
    raw_url = os.environ.get("DATABASE_URL")

    if not raw_url:
        raise SystemExit("BLOCKED: DATABASE_URL is required.")

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
        raise SystemExit(
            "BLOCKED: Database connection is not the approved "
            "isolated Phase 5E migration-test target."
        )

    engine = create_engine(url, pool_pre_ping=True)

    try:
        with engine.connect() as connection:
            database, username = connection.execute(
                text("SELECT current_database(), current_user")
            ).one()

            if (
                database != EXPECTED_DATABASE
                or username != EXPECTED_USER
            ):
                raise SystemExit(
                    "BLOCKED: Connected database identity mismatch."
                )

        print("PASS: Isolated migration-test database identity verified.")
        print("PASS: Database host, port, name and user verified.")
        print("No migrations executed.")

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
