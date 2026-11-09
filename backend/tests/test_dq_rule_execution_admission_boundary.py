"""Fail-closed boundary tests for legacy range execution.

These tests use mocks only. No client data, credentials, database
connections, or execution admission is activated.
"""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from app.services.data_quality_execution_capacity_policy import (
    ExecutionCapacityPolicyError,
)
from app.services.data_quality_rule_execution import execute_range_rule


def test_disabled_admission_blocks_legacy_execution_before_any_work():
    db = Mock()
    config = Mock()

    with patch(
        "app.core.config.settings.dq_execution_admission_enabled",
        False,
    ), patch(
        "app.services.data_quality_rule_execution.prepare_rule_execution",
    ) as prepare, patch(
        "app.services.postgresql_execution_authorization."
        "authorize_postgresql_execution_connection",
    ) as authorize, patch(
        "app.services.postgresql_execution_authorization."
        "revalidate_postgresql_execution_connection",
    ) as revalidate, patch(
        "app.services.data_quality_rule_execution.measure_prepared_range_rule",
    ) as measure, patch(
        "app.services.data_quality_rule_execution.record_successful_execution",
    ) as record:
        with pytest.raises(
            ExecutionCapacityPolicyError,
            match="disabled",
        ):
            execute_range_rule(
                db,
                project_id=uuid4(),
                rule_id=uuid4(),
                actor_user_id=uuid4(),
                config=config,
            )

    prepare.assert_not_called()
    authorize.assert_not_called()
    revalidate.assert_not_called()
    measure.assert_not_called()
    record.assert_not_called()
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_enabled_admission_still_blocks_legacy_execution_without_verified_protection():
    """A configuration flag is not proof of committed protection."""
    db = Mock()
    config = Mock()

    with patch(
        "app.core.config.settings.dq_execution_admission_enabled",
        True,
    ), patch(
        "app.core.config.settings.dq_execution_max_concurrent",
        2,
    ), patch(
        "app.services.data_quality_rule_execution.prepare_rule_execution",
    ) as prepare, patch(
        "app.services.postgresql_execution_authorization."
        "authorize_postgresql_execution_connection",
    ) as authorize, patch(
        "app.services.postgresql_execution_authorization."
        "revalidate_postgresql_execution_connection",
    ) as revalidate, patch(
        "app.services.data_quality_rule_execution.measure_prepared_range_rule",
    ) as measure, patch(
        "app.services.data_quality_rule_execution.record_successful_execution",
    ) as record:
        with pytest.raises(
            ExecutionCapacityPolicyError,
            match="verified protected coordination",
        ):
            execute_range_rule(
                db,
                project_id=uuid4(),
                rule_id=uuid4(),
                actor_user_id=uuid4(),
                config=config,
            )

    prepare.assert_not_called()
    authorize.assert_not_called()
    revalidate.assert_not_called()
    measure.assert_not_called()
    record.assert_not_called()
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
