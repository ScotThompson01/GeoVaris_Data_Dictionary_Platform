"""Isolated PostgreSQL persistence test for draft Data Quality rules."""

import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.project import Project
from app.models.data_source import DataSource
from app.models.source_object import SourceObject
from app.models.data_field import DataField
from app.models.data_quality_rule import DataQualityRule
from app.models.data_quality_rule_version import DataQualityRuleVersion


def test_draft_range_rule_persists_in_isolated_postgresql():
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
                client_id = uuid.uuid4()
                project_id = uuid.uuid4()
                source_id = uuid.uuid4()
                object_id = uuid.uuid4()
                field_id = uuid.uuid4()
                rule_id = uuid.uuid4()
                version_id = uuid.uuid4()

                with Session(bind=connection, join_transaction_mode="rollback_only") as db:
                    db.add(Client(
                        id=client_id,
                        name=f"DQ Integration Test {client_id.hex}",
                    ))
                    db.flush()

                    db.add(Project(
                        id=project_id,
                        client_id=client_id,
                        name="Synthetic DQ Project",
                    ))
                    db.flush()

                    db.add(DataSource(
                        id=source_id,
                        project_id=project_id,
                        name="Synthetic DQ Source",
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

                    db.add(DataQualityRule(
                        id=rule_id,
                        data_field_id=field_id,
                        rule_name="Latitude Range",
                        status="draft",
                        active_version_id=None,
                    ))
                    db.flush()

                    db.add(DataQualityRuleVersion(
                        id=version_id,
                        rule_id=rule_id,
                        version_number=1,
                        rule_type="range",
                        quality_dimension="validity",
                        min_value=Decimal("-90"),
                        max_value=Decimal("90"),
                        null_allowed=False,
                        status="draft",
                    ))
                    db.flush()

                    stored_rule = db.scalar(
                        select(DataQualityRule).where(
                            DataQualityRule.id == rule_id
                        )
                    )
                    stored_version = db.scalar(
                        select(DataQualityRuleVersion).where(
                            DataQualityRuleVersion.id == version_id
                        )
                    )

                    assert stored_rule is not None
                    assert stored_version is not None
                    assert stored_rule.data_field_id == field_id
                    assert stored_rule.status == "draft"
                    assert stored_rule.active_version_id is None
                    assert stored_version.rule_id == rule_id
                    assert stored_version.version_number == 1
                    assert stored_version.status == "draft"
                    assert stored_version.min_value == Decimal("-90")
                    assert stored_version.max_value == Decimal("90")
                    assert stored_version.null_allowed is False

            finally:
                transaction.rollback()
    finally:
        engine.dispose()
