"""Transactional approval tests against isolated PostgreSQL."""

import os
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.project import Project
from app.models.user import User
from app.models.project_access import ProjectAccess
from app.models.data_source import DataSource
from app.models.source_object import SourceObject
from app.models.data_field import DataField
from app.models.data_quality_rule import DataQualityRule
from app.models.data_quality_rule_version import DataQualityRuleVersion
from app.models.data_quality_rule_audit_event import DataQualityRuleAuditEvent
from app.services.data_quality_rule_approval import approve_dq_rule_version


@pytest.mark.integration
def test_approval_persists_audit_without_activating_rule():
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

                if revision != "0018":
                    pytest.fail(
                        f"Expected isolated database revision 0018, got {revision}."
                    )

                with Session(
                    bind=connection,
                    join_transaction_mode="rollback_only",
                    expire_on_commit=False,
                ) as db:
                    creator = User(
                        id=uuid.uuid4(),
                        username=f"dq_creator_{uuid.uuid4().hex}",
                        password_hash="test-only-placeholder",
                        is_active=True,
                        is_installation_admin=False,
                    )
                    approver = User(
                        id=uuid.uuid4(),
                        username=f"dq_approver_{uuid.uuid4().hex}",
                        password_hash="test-only-placeholder",
                        is_active=True,
                        is_installation_admin=False,
                    )
                    client = Client(
                        id=uuid.uuid4(),
                        name=f"Synthetic Approval Client {uuid.uuid4().hex}",
                    )
                    db.add_all([creator, approver, client])
                    db.flush()

                    project = Project(
                        id=uuid.uuid4(),
                        client_id=client.id,
                        name="Synthetic Approval Project",
                    )
                    db.add(project)
                    db.flush()

                    grant = ProjectAccess(
                        id=uuid.uuid4(),
                        user_id=approver.id,
                        project_id=project.id,
                        can_approve_dq_rules=True,
                    )
                    source = DataSource(
                        id=uuid.uuid4(),
                        project_id=project.id,
                        name="Synthetic Approval Source",
                        source_type="postgresql",
                        connection_mode="read_only",
                    )
                    db.add_all([grant, source])
                    db.flush()

                    source_object = SourceObject(
                        id=uuid.uuid4(),
                        data_source_id=source.id,
                        object_type="table",
                        object_name="synthetic_approval_table",
                    )
                    db.add(source_object)
                    db.flush()

                    field = DataField(
                        id=uuid.uuid4(),
                        source_object_id=source_object.id,
                        field_name="latitude",
                        ordinal_position=1,
                    )
                    db.add(field)
                    db.flush()

                    rule = DataQualityRule(
                        id=uuid.uuid4(),
                        data_field_id=field.id,
                        rule_name="Latitude valid range",
                        status="draft",
                    )
                    db.add(rule)
                    db.flush()

                    version = DataQualityRuleVersion(
                        id=uuid.uuid4(),
                        rule_id=rule.id,
                        created_by_user_id=creator.id,
                        version_number=1,
                        rule_type="range",
                        quality_dimension="validity",
                        min_value=-90,
                        max_value=90,
                        null_allowed=False,
                        status="draft",
                    )
                    db.add(version)
                    db.flush()

                    result = approve_dq_rule_version(
                        db,
                        project_id=project.id,
                        rule_id=rule.id,
                        version_id=version.id,
                        actor_user_id=approver.id,
                    )

                    assert result.id == version.id
                    assert result.status == "approved"

                    stored_version = db.get(
                        DataQualityRuleVersion, version.id
                    )
                    stored_rule = db.get(DataQualityRule, rule.id)

                    assert stored_version.status == "approved"
                    assert stored_rule.status == "draft"
                    assert stored_rule.active_version_id is None

                    events = db.scalars(
                        select(DataQualityRuleAuditEvent).where(
                            DataQualityRuleAuditEvent.rule_id == rule.id
                        )
                    ).all()

                    assert len(events) == 1
                    assert events[0].project_id == project.id
                    assert events[0].actor_user_id == approver.id
                    assert events[0].version_id == version.id
                    assert events[0].event_type == "version.approved"
                    assert events[0].old_status == "draft"
                    assert events[0].new_status == "approved"
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


@pytest.mark.integration
def test_approval_audit_failure_preserves_draft():
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

                if revision != "0018":
                    pytest.fail(
                        f"Expected isolated database revision 0018, got {revision}."
                    )

                with Session(
                    bind=connection,
                    join_transaction_mode="rollback_only",
                    expire_on_commit=False,
                ) as db:
                    creator = User(
                        id=uuid.uuid4(),
                        username=f"dq_creator_{uuid.uuid4().hex}",
                        password_hash="test-only-placeholder",
                        is_active=True,
                        is_installation_admin=False,
                    )
                    approver = User(
                        id=uuid.uuid4(),
                        username=f"dq_approver_{uuid.uuid4().hex}",
                        password_hash="test-only-placeholder",
                        is_active=True,
                        is_installation_admin=False,
                    )
                    client = Client(
                        id=uuid.uuid4(),
                        name=f"Synthetic Approval Client {uuid.uuid4().hex}",
                    )
                    db.add_all([creator, approver, client])
                    db.flush()

                    project = Project(
                        id=uuid.uuid4(),
                        client_id=client.id,
                        name="Synthetic Approval Project",
                    )
                    db.add(project)
                    db.flush()

                    grant = ProjectAccess(
                        id=uuid.uuid4(),
                        user_id=approver.id,
                        project_id=project.id,
                        can_approve_dq_rules=True,
                    )
                    source = DataSource(
                        id=uuid.uuid4(),
                        project_id=project.id,
                        name="Synthetic Approval Source",
                        source_type="postgresql",
                        connection_mode="read_only",
                    )
                    db.add_all([grant, source])
                    db.flush()

                    source_object = SourceObject(
                        id=uuid.uuid4(),
                        data_source_id=source.id,
                        object_type="table",
                        object_name="synthetic_approval_table",
                    )
                    db.add(source_object)
                    db.flush()

                    field = DataField(
                        id=uuid.uuid4(),
                        source_object_id=source_object.id,
                        field_name="latitude",
                        ordinal_position=1,
                    )
                    db.add(field)
                    db.flush()

                    rule = DataQualityRule(
                        id=uuid.uuid4(),
                        data_field_id=field.id,
                        rule_name="Latitude valid range",
                        status="draft",
                    )
                    db.add(rule)
                    db.flush()

                    version = DataQualityRuleVersion(
                        id=uuid.uuid4(),
                        rule_id=rule.id,
                        created_by_user_id=creator.id,
                        version_number=1,
                        rule_type="range",
                        quality_dimension="validity",
                        min_value=-90,
                        max_value=90,
                        null_allowed=False,
                        status="draft",
                    )
                    db.add(version)
                    db.flush()

                    # Force the audit insert to violate its event-type constraint.
                    # The version update must not survive this failed transaction.
                    from unittest.mock import patch
                    from sqlalchemy.exc import IntegrityError

                    def add_invalid_audit(instance):
                        if isinstance(instance, DataQualityRuleAuditEvent):
                            instance.event_type = "invalid.approval.event"
                        return approval_db_add(instance)

                    # Preserve synthetic setup records in the outer transaction.
                    # The approval attempt uses its own database savepoint.
                    with Session(
                        bind=connection,
                        join_transaction_mode="create_savepoint",
                        expire_on_commit=False,
                    ) as approval_db:
                        approval_db_add = approval_db.add
                        with patch.object(
                            approval_db,
                            "add",
                            side_effect=add_invalid_audit,
                        ):
                            with pytest.raises(IntegrityError):
                                approve_dq_rule_version(
                                    approval_db,
                                    project_id=project.id,
                                    rule_id=rule.id,
                                    version_id=version.id,
                                    actor_user_id=approver.id,
                                )

                    with Session(
                        bind=connection,
                        join_transaction_mode="rollback_only",
                        expire_on_commit=False,
                    ) as verify_db:
                        stored_version = verify_db.get(
                            DataQualityRuleVersion, version.id
                        )
                        assert stored_version.status == "draft"

                        events = verify_db.scalars(
                            select(DataQualityRuleAuditEvent).where(
                                DataQualityRuleAuditEvent.rule_id == rule.id
                            )
                        ).all()
                        assert events == []
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
