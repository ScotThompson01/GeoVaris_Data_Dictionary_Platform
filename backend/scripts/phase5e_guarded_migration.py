"""Guarded Alembic upgrade for the isolated Phase 5E test database only."""

import os
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from app.core.config import settings
from scripts.phase5e_migration_preflight import main as verify_database

AUTHORIZATION_FLAG = "--execute-isolated-upgrade"


def main() -> None:
    if sys.argv[1:] != [AUTHORIZATION_FLAG]:
        raise SystemExit(
            "BLOCKED: Explicit isolated-upgrade authorization is required."
        )

    environment_url = os.environ.get("DATABASE_URL")
    if not environment_url:
        raise SystemExit("BLOCKED: DATABASE_URL is required.")

    if make_url(settings.database_url) != make_url(environment_url):
        raise SystemExit(
            "BLOCKED: Alembic and preflight database targets differ."
        )

    verify_database()

    config = Config("alembic.ini")
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
