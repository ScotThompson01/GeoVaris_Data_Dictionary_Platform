"""Cross-project Data Quality rule authorization against isolated PostgreSQL."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.db.session import get_db
from app.main import app
from app.models.client import Client
from app.models.project import Project
from app.models.project_access import ProjectAccess
from app.models.data_source import DataSource
from app.models.source_object import SourceObject
from app.models.data_field import DataField
from app.models.data_quality_rule import DataQualityRule
from app.models.data_quality_rule_version import DataQualityRuleVersion
from app.models.user import User


def test_get_rules_denies_access_to_other_project_in_postgresql():
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
                        username=f"dq_cross_project_{uuid.uuid4().hex}",
                        password_hash="test-only-placeholder",
                        is_active=True,
                        is_installation_admin=False,
                    )
                    client_id = uuid.uuid4()
                    allowed_project_id = uuid.uuid4()
                    denied_project_id = uuid.uuid4()

                    db.add(user)
                    db.add(Client(
                        id=client_id,
                        name=f"DQ Cross-Project Test {client_id.hex}",
                    ))
                    db.flush()

                    db.add_all([
                        Project(
                            id=allowed_project_id,
                            client_id=client_id,
                            name="Authorized Test Project",
                        ),
                        Project(
                            id=denied_project_id,
                            client_id=client_id,
                            name="Restricted Test Project",
                        ),
                    ])
                    db.flush()

                    db.add(ProjectAccess(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        project_id=allowed_project_id,
                    ))
                    db.flush()

                    field_ids = {}
                    rule_ids = {}

                    for label, project_id in [
                        ("allowed", allowed_project_id),
                        ("denied", denied_project_id),
                    ]:
                        source_id = uuid.uuid4()
                        object_id = uuid.uuid4()
                        field_id = uuid.uuid4()
                        rule_id = uuid.uuid4()

                        db.add(DataSource(
                            id=source_id,
                            project_id=project_id,
                            name=f"Synthetic {label} Source",
                            source_type="postgresql",
                            connection_mode="read_only",
                        ))
                        db.flush()

                        db.add(SourceObject(
                            id=object_id,
                            data_source_id=source_id,
                            object_type="table",
                            object_name=f"synthetic_{label}_locations",
                        ))
                        db.flush()

                        db.add(DataField(
                            id=field_id,
                            source_object_id=object_id,
                            field_name="latitude",
                            ordinal_position=1,
                        ))
                        db.flush()

                        db.add(DataQualityRule(
                            id=rule_id,
                            data_field_id=field_id,
                            rule_name=f"{label.title()} Latitude Range",
                            status="draft",
                            active_version_id=None,
                        ))
                        db.flush()

                        db.add(DataQualityRuleVersion(
                            id=uuid.uuid4(),
                            rule_id=rule_id,
                            version_number=1,
                            rule_type="range",
                            quality_dimension="validity",
                            min_value=-90,
                            max_value=90,
                            null_allowed=False,
                            status="draft",
                        ))
                        db.flush()

                        field_ids[label] = field_id
                        rule_ids[label] = rule_id

                    def override_get_db():
                        yield db

                    def override_authentication():
                        return AuthenticatedSession(
                            user=user,
                            token="dq-cross-project-test-only-token",
                        )

                    previous_overrides = app.dependency_overrides.copy()
                    app.dependency_overrides[get_db] = override_get_db
                    app.dependency_overrides[require_authenticated_session] = (
                        override_authentication
                    )

                    try:
                        with TestClient(app) as test_client:
                            allowed_response = test_client.get(
                                "/api/v1/data-quality-rules",
                                params={
                                    "data_field_id": str(field_ids["allowed"])
                                },
                            )
                            denied_response = test_client.get(
                                "/api/v1/data-quality-rules",
                                params={
                                    "data_field_id": str(field_ids["denied"])
                                },
                            )

                        assert allowed_response.status_code == 200, (
                            allowed_response.text
                        )
                        allowed_rules = allowed_response.json()
                        assert len(allowed_rules) == 1
                        assert allowed_rules[0]["rule_id"] == str(
                            rule_ids["allowed"]
                        )

                        assert denied_response.status_code == 404, (
                            denied_response.text
                        )
                        assert denied_response.json()["detail"] == (
                            "Data field not found."
                        )
                    finally:
                        app.dependency_overrides.clear()
                        app.dependency_overrides.update(previous_overrides)
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
