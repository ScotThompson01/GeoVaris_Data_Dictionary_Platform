"""Verify field-level isolation using the isolated PostgreSQL test database."""

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
from app.models.data_source import DataSource
from app.models.source_object import SourceObject
from app.models.data_field import DataField
from app.models.data_quality_rule import DataQualityRule
from app.models.data_quality_rule_version import DataQualityRuleVersion
from app.models.project_access import ProjectAccess
from app.models.user import User


def test_get_rules_isolated_by_field_in_postgresql():
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
                        username=f"dq_isolation_{uuid.uuid4().hex}",
                        password_hash="test-only-placeholder",
                        is_active=True,
                        is_installation_admin=False,
                    )

                    client_id = uuid.uuid4()
                    project_id = uuid.uuid4()
                    source_id = uuid.uuid4()
                    object_id = uuid.uuid4()
                    latitude_field_id = uuid.uuid4()
                    longitude_field_id = uuid.uuid4()

                    db.add(user)
                    db.add(Client(
                        id=client_id,
                        name=f"DQ Isolation Test {client_id.hex}",
                    ))
                    db.flush()

                    db.add(Project(
                        id=project_id,
                        client_id=client_id,
                        name="Synthetic Isolation Project",
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
                        name="Synthetic Isolation Source",
                        source_type="postgresql",
                        connection_mode="read_only",
                    ))
                    db.flush()

                    db.add(SourceObject(
                        id=object_id,
                        data_source_id=source_id,
                        object_type="table",
                        object_name="synthetic_coordinates",
                    ))
                    db.flush()

                    db.add_all([
                        DataField(
                            id=latitude_field_id,
                            source_object_id=object_id,
                            field_name="latitude",
                            ordinal_position=1,
                        ),
                        DataField(
                            id=longitude_field_id,
                            source_object_id=object_id,
                            field_name="longitude",
                            ordinal_position=2,
                        ),
                    ])
                    db.flush()

                    latitude_rule_id = uuid.uuid4()
                    longitude_rule_id = uuid.uuid4()

                    db.add_all([
                        DataQualityRule(
                            id=latitude_rule_id,
                            data_field_id=latitude_field_id,
                            rule_name="Latitude Range",
                            status="draft",
                            active_version_id=None,
                        ),
                        DataQualityRule(
                            id=longitude_rule_id,
                            data_field_id=longitude_field_id,
                            rule_name="Longitude Range",
                            status="draft",
                            active_version_id=None,
                        ),
                    ])
                    db.flush()

                    db.add_all([
                        DataQualityRuleVersion(
                            id=uuid.uuid4(),
                            rule_id=latitude_rule_id,
                            version_number=1,
                            rule_type="range",
                            quality_dimension="validity",
                            min_value=-90,
                            max_value=90,
                            null_allowed=False,
                            status="draft",
                        ),
                        DataQualityRuleVersion(
                            id=uuid.uuid4(),
                            rule_id=longitude_rule_id,
                            version_number=1,
                            rule_type="range",
                            quality_dimension="validity",
                            min_value=-180,
                            max_value=180,
                            null_allowed=False,
                            status="draft",
                        ),
                    ])
                    db.flush()

                    def override_get_db():
                        yield db

                    def override_authentication():
                        return AuthenticatedSession(
                            user=user,
                            token="dq-isolation-test-only-token",
                        )

                    app.dependency_overrides[get_db] = override_get_db
                    app.dependency_overrides[require_authenticated_session] = (
                        override_authentication
                    )

                    try:
                        with TestClient(app) as test_client:
                            latitude_response = test_client.get(
                                "/api/v1/data-quality-rules",
                                params={
                                    "data_field_id": str(latitude_field_id)
                                },
                            )
                            longitude_response = test_client.get(
                                "/api/v1/data-quality-rules",
                                params={
                                    "data_field_id": str(longitude_field_id)
                                },
                            )

                        assert latitude_response.status_code == 200
                        assert longitude_response.status_code == 200

                        latitude_rules = latitude_response.json()
                        longitude_rules = longitude_response.json()

                        assert len(latitude_rules) == 1
                        assert len(longitude_rules) == 1

                        assert latitude_rules[0]["rule_id"] == str(
                            latitude_rule_id
                        )
                        assert latitude_rules[0]["data_field_id"] == str(
                            latitude_field_id
                        )
                        assert latitude_rules[0]["rule_name"] == "Latitude Range"

                        assert longitude_rules[0]["rule_id"] == str(
                            longitude_rule_id
                        )
                        assert longitude_rules[0]["data_field_id"] == str(
                            longitude_field_id
                        )
                        assert longitude_rules[0]["rule_name"] == "Longitude Range"

                        assert latitude_rules[0]["active_version_id"] is None
                        assert longitude_rules[0]["active_version_id"] is None

                        assert len(latitude_rules[0]["versions"]) == 1
                        assert len(longitude_rules[0]["versions"]) == 1
                    finally:
                        app.dependency_overrides.pop(get_db, None)
                        app.dependency_overrides.pop(
                            require_authenticated_session, None
                        )
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
