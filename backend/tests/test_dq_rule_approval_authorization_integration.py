"""Data Quality approval authorization against isolated PostgreSQL."""

import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.project import Project
from app.models.project_access import ProjectAccess
from app.models.user import User
from app.services.project_authorization import require_dq_rule_approver


def test_dq_approval_permission_is_enforced_in_postgresql():
    database_url = os.environ.get("AUTH_TEST_DATABASE_URL")

    if not database_url:
        pytest.skip("AUTH_TEST_DATABASE_URL is not configured.")

    parsed_url = make_url(database_url)

    if (
        parsed_url.drivername != "postgresql+psycopg"
        or parsed_url.host != "auth_test_db"
        or parsed_url.database != "geovaris_auth_test"
        or parsed_url.username != "geovaris_auth_test"
    ):
        pytest.fail("Refusing to run against a non-isolated database.")

    engine = create_engine(database_url, pool_pre_ping=True)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()

            try:
                with Session(
                    bind=connection,
                    join_transaction_mode="rollback_only",
                    expire_on_commit=False,
                ) as db:
                    user = User(
                        id=uuid.uuid4(),
                        username=f"dq_approval_test_{uuid.uuid4().hex}",
                        password_hash="test-only-placeholder",
                        is_active=True,
                        is_installation_admin=False,
                    )
                    client = Client(
                        id=uuid.uuid4(),
                        name="Synthetic DQ Approval Test Client",
                    )

                    db.add_all([user, client])
                    db.flush()

                    project = Project(
                        id=uuid.uuid4(),
                        client_id=client.id,
                        name="Synthetic DQ Approval Test Project",
                    )
                    db.add(project)
                    db.flush()

                    with pytest.raises(HTTPException) as exc:
                        require_dq_rule_approver(
                            db,
                            user_id=user.id,
                            project_id=project.id,
                        )
                    assert exc.value.status_code == 404

                    grant = ProjectAccess(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        project_id=project.id,
                    )
                    db.add(grant)
                    db.flush()

                    assert grant.can_approve_dq_rules is False

                    with pytest.raises(HTTPException) as exc:
                        require_dq_rule_approver(
                            db,
                            user_id=user.id,
                            project_id=project.id,
                        )
                    assert exc.value.status_code == 403

                    grant.can_approve_dq_rules = True
                    db.flush()

                    assert require_dq_rule_approver(
                        db,
                        user_id=user.id,
                        project_id=project.id,
                    ) is None
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
