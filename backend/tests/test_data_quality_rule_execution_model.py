"""Metadata tests for Data Quality rule execution persistence."""

import app.db.base  # noqa: F401 - registers application models
from app.db.session import Base


def test_execution_table_is_registered_with_required_columns():
    table = Base.metadata.tables["data_quality_rule_executions"]

    assert {
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
    }.issubset(table.columns.keys())

def test_execution_project_and_actor_references_restrict_deletion():
    table = Base.metadata.tables["data_quality_rule_executions"]

    assert any(
        fk.parent.name == "project_id"
        and fk.target_fullname == "projects.id"
        and fk.ondelete == "RESTRICT"
        for fk in table.foreign_keys
    )
    assert any(
        fk.parent.name == "actor_user_id"
        and fk.target_fullname == "users.id"
        and fk.ondelete == "RESTRICT"
        for fk in table.foreign_keys
    )


def test_execution_version_reference_is_scoped_to_parent_rule():
    table = Base.metadata.tables["data_quality_rule_executions"]

    constraints = [
        constraint
        for constraint in table.foreign_key_constraints
        if constraint.name == "fk_dq_execution_rule_version_identity"
    ]

    assert len(constraints) == 1

    constraint = constraints[0]
    assert constraint.ondelete == "RESTRICT"
    assert {
        (element.parent.name, element.target_fullname)
        for element in constraint.elements
    } == {
        ("rule_id", "data_quality_rule_versions.rule_id"),
        ("version_id", "data_quality_rule_versions.id"),
    }

def test_execution_status_and_count_constraints_are_present():
    from sqlalchemy import CheckConstraint

    table = Base.metadata.tables["data_quality_rule_executions"]
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert {
        "ck_dq_execution_status",
        "ck_dq_execution_total_nonnegative",
        "ck_dq_execution_passing_nonnegative",
        "ck_dq_execution_violations_nonnegative",
        "ck_dq_execution_success_counts",
    }.issubset(constraints)

    assert "'succeeded'" in constraints["ck_dq_execution_status"]
    assert "'failed'" in constraints["ck_dq_execution_status"]
    assert "total_count = passing_count + violation_count" in (
        " ".join(constraints["ck_dq_execution_success_counts"].split())
    )

def test_execution_counts_use_64_bit_integers():
    from sqlalchemy import BigInteger

    table = Base.metadata.tables["data_quality_rule_executions"]

    for column_name in (
        "total_count",
        "passing_count",
        "violation_count",
    ):
        column = table.columns[column_name]
        assert isinstance(column.type, BigInteger), (
            f"{column_name} must use BigInteger for large datasets"
        )
        assert column.nullable is True