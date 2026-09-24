"""Interactively authorize the first installation administrator."""

import getpass
import sys

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.passwords import verify_password
from app.db.session import SessionLocal
from app.models.user import User


def bootstrap_installation_admin() -> int:
    """Grant the first administrator role to a verified existing user."""
    username = input("Existing username: ").strip()
    if not username:
        print("Username is required.")
        return 1

    password = getpass.getpass("Password for this account: ")

    try:
        with SessionLocal() as db:
            # Serialize concurrent bootstrap attempts in PostgreSQL.
            db.execute(text("SELECT pg_advisory_xact_lock(481902, 2)"))

            existing_admin = db.scalar(
                select(User.id)
                .where(User.is_installation_admin.is_(True))
                .limit(1)
            )
            if existing_admin is not None:
                print("An installation administrator already exists.")
                return 1

            user = db.scalar(
                select(User).where(User.username == username)
            )
            if (
                user is None
                or not user.is_active
                or not verify_password(password, user.password_hash)
            ):
                print("Account verification failed.")
                return 1

            user.is_installation_admin = True
            db.commit()

    except SQLAlchemyError:
        print("Administrator setup failed due to a database error.")
        return 1

    finally:
        del password

    print("First installation administrator configured.")
    return 0


if __name__ == "__main__":
    sys.exit(bootstrap_installation_admin())
