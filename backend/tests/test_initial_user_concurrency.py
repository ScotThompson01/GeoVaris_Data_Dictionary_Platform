"""Verify PostgreSQL serializes competing initial-user transactions.

This test runs only against the disposable auth_test_db database.
It tests the locking and existence-check sequence used by the setup command.
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models.user import User


LOCK_SQL = text("SELECT pg_advisory_xact_lock(481902, 1)")


def test_concurrent_initial_user_transactions_create_only_one_user():
    database_url = os.environ.get("AUTH_TEST_DATABASE_URL")

    if not database_url:
        pytest.skip("AUTH_TEST_DATABASE_URL is not configured.")

    parsed_url = make_url(database_url)

    if (
        parsed_url.host != "auth_test_db"
        or parsed_url.database != "geovaris_auth_test"
        or parsed_url.username != "geovaris_auth_test"
    ):
        pytest.fail("Refusing to run against a non-isolated database.")

    engine = create_engine(database_url)
    start = threading.Barrier(2)

    try:
        with Session(engine) as db:
            if db.scalar(select(User.id).limit(1)) is not None:
                pytest.fail("Test database already contains a user.")

        def attempt(username: str) -> bool:
            start.wait(timeout=10)

            with Session(engine) as db:
                db.execute(LOCK_SQL)

                if db.scalar(select(User.id).limit(1)) is not None:
                    return False

                db.add(
                    User(
                        username=username,
                        password_hash="$argon2id$test-only-placeholder",
                        is_active=True,
                    )
                )
                db.commit()
                return True

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(attempt, "concurrency_test_a")
            second = executor.submit(attempt, "concurrency_test_b")
            results = [first.result(timeout=20), second.result(timeout=20)]

        with Session(engine) as db:
            users = db.scalars(select(User)).all()

        assert sorted(results) == [False, True]
        assert len(users) == 1

    finally:
        engine.dispose()