"""PostgreSQL integrity tests for Data Quality rule audit events."""

import importlib.util
import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.models.client import Client
from app.models.project import Project
from app.models.user import User
from app.models.data_field import DataField
from app.models.data_source import DataSource
from app.models.source_object import SourceObject
from app.models.data_quality_rule import DataQualityRule
from app.models.data_quality_rule_version import DataQualityRuleVersion


@pytest.mark.integration
def test_audit_rejects_version_belonging_to_another_rule():
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
                revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()

                if revision != "0016":
                    pytest.fail(
                        f"Expected isolated test database at 0016, got {revision}."
                    )
                with Session(
                    bind=connection,
                    join_transaction_mode="rollback_only",
                    expire_on_commit=False,
                ) as db:
                    user = User(
                        id=uuid.uuid4(),
                        username=f"dq_audit_{uuid.uuid4().hex}",
                        password_hash="test-only-placeholder",
                        is_active=True,
                        is_installation_admin=False,
                    )
                    client = Client(
                        id=uuid.uuid4(),
                        name=f"DQ Audit Test {uuid.uuid4().hex}",
                    )
                    db.add_all([user, client])
                    db.flush()

                    project = Project(
                        id=uuid.uuid4(),
                        client_id=client.id,
                        name="Synthetic Audit Integrity Project",
                    )
                    db.add(project)
                    db.flush()

                    source = DataSource(
                        id=uuid.uuid4(),
                        project_id=project.id,
                        name="Synthetic Audit Source",
                        source_type="postgresql",
                        connection_mode="read_only",
                    )
                    db.add(source)
                    db.flush()

                    source_object = SourceObject(
                        id=uuid.uuid4(),
                        data_source_id=source.id,
                        object_type="table",
                        object_name="synthetic_audit_table",
                    )
                    db.add(source_object)
                    db.flush()

                    field_a = DataField(
                        id=uuid.uuid4(),
                        source_object_id=source_object.id,
                        field_name="field_a",
                        ordinal_position=1,
                    )
                    field_b = DataField(
                        id=uuid.uuid4(),
                        source_object_id=source_object.id,
                        field_name="field_b",
                        ordinal_position=2,
                    )
                    db.add_all([field_a, field_b])
                    db.flush()

                    rule_a = DataQualityRule(
                        id=uuid.uuid4(),
                        data_field_id=field_a.id,
                        rule_name="Rule A",
                        status="draft",
                    )
                    rule_b = DataQualityRule(
                        id=uuid.uuid4(),
                        data_field_id=field_b.id,
                        rule_name="Rule B",
                        status="draft",
                    )
                    db.add_all([rule_a, rule_b])
                    db.flush()

                    version_a = DataQualityRuleVersion(
                        id=uuid.uuid4(),
                        rule_id=rule_a.id,
                        version_number=1,
                        rule_type="range",
                        quality_dimension="validity",
                        min_value=0,
                        max_value=10,
                        null_allowed=False,
                        status="draft",
                    )
                    version_b = DataQualityRuleVersion(
                        id=uuid.uuid4(),
                        rule_id=rule_b.id,
                        version_number=1,
                        rule_type="range",
                        quality_dimension="validity",
                        min_value=0,
                        max_value=10,
                        null_allowed=False,
                        status="draft",
                    )
                    db.add_all([version_a, version_b])
                    db.flush()

                    integrity_error_raised = False
                    try:
                        with db.begin_nested():
                            db.execute(
                                text(
                                    """
                                    INSERT INTO data_quality_rule_audit_events
                                        (id, project_id, actor_user_id, rule_id,
                                         version_id, event_type, old_status,
                                         new_status)
                                    VALUES
                                        (:id, :project_id, :actor_user_id, :rule_id,
                                         :version_id, :event_type, :old_status,
                                         :new_status)
                                    """
                                ),
                                {
                                    "id": str(uuid.uuid4()),
                                    "project_id": str(project.id),
                                    "actor_user_id": str(user.id),
                                    "rule_id": str(rule_a.id),
                                    "version_id": str(version_b.id),
                                    "event_type": "version.approved",
                                    "old_status": "draft",
                                    "new_status": "approved",
                                },
                            )


                    except IntegrityError:
                        integrity_error_raised = True

                    assert integrity_error_raised, "PostgreSQL accepted a mismatched rule/version audit reference."
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
