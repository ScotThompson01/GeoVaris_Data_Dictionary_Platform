"""Phase 5E execution lifecycle database contract tests.

These tests inspect SQLAlchemy metadata only.
They do not connect to or modify any database.
"""

from sqlalchemy import CheckConstraint

from app.models.data_quality_rule_execution import DataQualityRuleExecution


def _constraint_sql(name: str) -> str:
    constraints = [
        constraint
        for constraint in DataQualityRuleExecution.__table__.constraints
        if isinstance(constraint, CheckConstraint)
        and constraint.name == name
    ]
    assert len(constraints) == 1, f"Expected one constraint named {name}"
    return str(constraints[0].sqltext).lower()


def test_execution_status_constraint_supports_seven_approved_states():
    sql = _constraint_sql("ck_dq_execution_status")

    for status in (
        "pending",
        "running",
        "succeeded",
        "failed",
        "incomplete",
        "status_uncertain",
        "cancelled",
    ):
        assert f"'{status}'" in sql


def test_pending_execution_does_not_require_start_timestamp():
    table = DataQualityRuleExecution.__table__

    assert table.c.started_at.nullable is True
    assert table.c.created_at.nullable is False


def test_successful_execution_still_requires_balanced_counts():
    sql = _constraint_sql("ck_dq_execution_success_counts")

    assert "succeeded" in sql
    assert "total_count is not null" in sql
    assert "passing_count is not null" in sql
    assert "violation_count is not null" in sql
    assert "total_count = passing_count + violation_count" in sql


def test_existing_execution_identity_and_history_columns_are_preserved():
    table = DataQualityRuleExecution.__table__

    expected_columns = {
        "id",
        "project_id",
        "actor_user_id",
        "rule_id",
        "version_id",
        "status",
        "total_count",
        "passing_count",
        "violation_count",
        "error_code",
        "started_at",
        "completed_at",
        "created_at",
    }

    assert expected_columns.issubset(set(table.columns.keys()))
    assert table.c.completed_at.nullable is True
