"""Interactively create the first local GeoVaris user."""

import getpass
import sys

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.passwords import hash_password
from app.db.session import SessionLocal
from app.models.user import User


def create_initial_user() -> int:
    """Create one initial local account; refuse if any user already exists."""

    username = input("Initial username: ").strip()

    if not 3 <= len(username) <= 150:
        print("Username must contain between 3 and 150 characters.")
        return 1

    if not all(
        character.isascii()
        and (character.isalnum() or character in "._-")
        for character in username
    ):
        print("Username may contain only ASCII letters, numbers, ., _ and -.")
        return 1

    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")

    if password != confirmation:
        print("Passwords do not match.")
        return 1

    if len(password) < 12 or len(password.encode("utf-8")) > 1024:
        print("Password must contain at least 12 characters and at most 1024 bytes.")
        return 1

    try:
        with SessionLocal() as db:
            # PostgreSQL transaction-level advisory lock prevents two
            # setup processes from creating the first account concurrently.
            # Keep the lock and user-existence check in the same transaction.
            db.execute(text("SELECT pg_advisory_xact_lock(481902, 1)"))

            if db.scalar(select(User.id).limit(1)) is not None:
                print("Initial setup is unavailable: a local user already exists.")
                return 1

            user = User(
                username=username,
                password_hash=hash_password(password),
                is_active=True,
            )

            db.add(user)
            db.commit()

    except IntegrityError:
        print("Initial account could not be created.")
        return 1

    except SQLAlchemyError:
        print("Initial account setup failed due to a database error.")
        return 1

    finally:
        # Do not print or log passwords or password hashes.
        del password
        del confirmation

    print("Initial local user created.")
    return 0


if __name__ == "__main__":
    sys.exit(create_initial_user())