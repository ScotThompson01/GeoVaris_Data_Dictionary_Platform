"""End-to-end API persistence test against isolated PostgreSQL."""

import os
import uuid
from decimal import Decimal

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
from app.models.data_source import DataSource
from app.models.source_object import SourceObject
from app.models.data_field import DataField
from app.models.data_quality_rule import DataQualityRule
from app.models.data_quality_rule_version import DataQualityRuleVersion
from app.models.project_access import ProjectAccess
from app.models.user import User


def test_authorized_api_creates_inactive_draft_in_postgresql():
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
                        username=f"dq_api_test_{uuid.uuid4().hex}",
                        password_hash="test-only-placeholder",
                        is_active=True,
                        is_installation_admin=False,
                    )
                    client_id = uuid.uuid4()
                    project_id = uuid.uuid4()
                    source_id = uuid.uuid4()
                    object_id = uuid.uuid4()
                    field_id = uuid.uuid4()

                    db.add(user)
                    db.add(Client(
                        id=client_id,
                        name=f"DQ API Test {client_id.hex}",
                    ))
                    db.flush()

                    db.add(Project(
                        id=project_id,
                        client_id=client_id,
                        name="Synthetic DQ API Project",
                    ))
                    db.flush()

                    db.add(ProjectAccess(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        project_id=project_id,
                    ))
                    db.add(DataSource(
                        id=source_id,
                        project_id=project_id,
                        name="Synthetic DQ API Source",
                        source_type="postgresql",
                        connection_mode="read_only",
                    ))
                    db.flush()

                    db.add(SourceObject(
                        id=object_id,
                        data_source_id=source_id,
                        object_type="table",
                        object_name="synthetic_locations",
                    ))
                    db.flush()

                    db.add(DataField(
                        id=field_id,
                        source_object_id=object_id,
                        field_name="latitude",
                        ordinal_position=1,
                    ))
                    db.flush()

                    def override_get_db():
                        yield db

                    def override_authentication():
                        return AuthenticatedSession(
                            user=user,
                            token="dq-api-integration-test-only-token",
                        )

                    app.dependency_overrides[get_db] = override_get_db
                    app.dependency_overrides[require_authenticated_session] = (
                        override_authentication
                    )

                    try:
                        with TestClient(app) as test_client:
                            response = test_client.post(
                                "/api/v1/data-quality-rules",
                                json={
                                    "data_field_id": str(field_id),
                                    "rule_name": "Latitude Range",
                                    "min_value": "-90",
                                    "max_value": "90",
                                    "null_allowed": False,
                                },
                            )

                        assert response.status_code == 201, response.text
                        result = response.json()

                        rule = db.get(
                            DataQualityRule,
                            uuid.UUID(result["rule_id"]),
                        )
                        version = db.get(
                            DataQualityRuleVersion,
                            uuid.UUID(result["version_id"]),
                        )

                        assert rule is not None
                        assert version is not None
                        assert rule.data_field_id == field_id
                        assert rule.status == "draft"
                        assert rule.active_version_id is None
                        assert version.rule_id == rule.id
                        assert version.version_number == 1
                        assert version.status == "draft"
                        assert version.min_value == Decimal("-90")
                        assert version.max_value == Decimal("90")
                        assert version.null_allowed is False
                    finally:
                        app.dependency_overrides.pop(get_db, None)
                        app.dependency_overrides.pop(
                            require_authenticated_session, None
                        )
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
