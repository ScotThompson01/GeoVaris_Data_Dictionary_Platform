"""Rollback-only Phase 5E execution persistence integration test.

Requires explicit opt-in and the isolated Phase 5E PostgreSQL database.
Never runs against the main or authentication databases.
"""

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.project import Project
from app.models.user import User
from app.models.data_source import DataSource
from app.models.source_object import SourceObject
from app.models.data_field import DataField
from app.models.data_quality_rule import DataQualityRule
from app.models.data_quality_rule_version import DataQualityRuleVersion
from app.models.data_quality_rule_execution import DataQualityRuleExecution
from app.services.data_quality_execution_persistence import (
    stage_pending_execution,
    stage_running_execution,
)


@pytest.mark.integration
def test_pending_to_running_persists_and_rolls_back():
    if os.environ.get("GEOVARIS_PHASE5E_INTEGRATION_TEST") != "1":
        pytest.skip("Phase 5E isolated integration test not enabled.")

    from scripts.phase5e_migration_preflight import main as verify_database

    # Fail closed unless the connection matches the approved isolated target.
    verify_database()

    engine = create_engine(
        os.environ["DATABASE_URL"],
        pool_pre_ping=True,
    )
    execution_id = None

    try:
        with engine.connect() as connection:
            transaction = connection.begin()

            try:
                client_id = uuid.uuid4()
                project_id = uuid.uuid4()
                user_id = uuid.uuid4()
                source_id = uuid.uuid4()
                object_id = uuid.uuid4()
                field_id = uuid.uuid4()
                rule_id = uuid.uuid4()
                version_id = uuid.uuid4()

                with Session(
                    bind=connection,
                    join_transaction_mode="rollback_only",
                ) as db:
                    db.add(Client(
                        id=client_id,
                        name=f"Phase 5E synthetic {client_id.hex}",
                    ))
                    db.flush()

                    db.add(Project(
                        id=project_id,
                        client_id=client_id,
                        name="Phase 5E rollback test",
                    ))
                    db.add(User(
                        id=user_id,
                        username=f"phase5e_{user_id.hex}",
                        password_hash="synthetic-test-only-placeholder",
                        is_active=True,
                    ))
                    db.flush()

                    db.add(DataSource(
                        id=source_id,
                        project_id=project_id,
                        name="Synthetic source - no connection",
                        source_type="postgresql",
                        connection_mode="read_only",
                    ))
                    db.flush()

                    db.add(SourceObject(
                        id=object_id,
                        data_source_id=source_id,
                        object_type="table",
                        object_name="synthetic_test_object",
                    ))
                    db.flush()

                    db.add(DataField(
                        id=field_id,
                        source_object_id=object_id,
                        field_name="test_value",
                        ordinal_position=1,
                    ))
                    db.flush()

                    db.add(DataQualityRule(
                        id=rule_id,
                        data_field_id=field_id,
                        rule_name="Phase 5E synthetic range rule",
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
                        min_value=Decimal("0"),
                        max_value=Decimal("100"),
                        status="draft",
                    ))
                    db.flush()

                    prepared = {
                        "rule": SimpleNamespace(id=rule_id),
                        "version": SimpleNamespace(
                            id=version_id,
                            rule_id=rule_id,
                        ),
                    }

                    execution = stage_pending_execution(
                        db,
                        prepared=prepared,
                        project_id=project_id,
                        actor_user_id=user_id,
                    )
                    execution_id = execution.id

                    assert execution.status == "pending"
                    assert execution.started_at is None

                    started_at = datetime.now(timezone.utc)
                    from unittest.mock import patch
                    from app.services.data_quality_execution_persistence import (
                        stage_authorized_running_execution,
                    )

                    with patch(
                        "app.services.project_authorization."
                        "require_dq_rule_executor"
                    ):
                        running = stage_authorized_running_execution(
                            db,
                            project_id=project_id,
                            execution_id=execution_id,
                            actor_user_id=user_id,
                            started_at=started_at,
                        )

                    assert running.id == execution_id

                    db.expire_all()

                    stored = db.scalar(
                        select(DataQualityRuleExecution).where(
                            DataQualityRuleExecution.id == execution_id
                        )
                    )

                    assert stored is not None
                    assert stored.status == "running"
                    assert stored.started_at is not None
                    assert stored.total_count is None
                    assert stored.passing_count is None
                    assert stored.violation_count is None
                    assert stored.completed_at is None

            finally:
                transaction.rollback()

        with engine.connect() as verification:
            assert verification.scalar(
                select(DataQualityRuleExecution.id).where(
                    DataQualityRuleExecution.id == execution_id
                )
            ) is None

    finally:
        engine.dispose()
