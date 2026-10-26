"""Structural tests for Data Quality rule lifecycle audit events."""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint

from app.models.data_quality_rule_audit_event import DataQualityRuleAuditEvent


def test_rule_audit_table_has_required_columns():
    table = DataQualityRuleAuditEvent.__table__

    assert table.name == "data_quality_rule_audit_events"
    assert {
        "id",
        "project_id",
        "actor_user_id",
        "rule_id",
        "version_id",
        "event_type",
        "old_status",
        "new_status",
        "created_at",
    } == set(table.columns.keys())


def test_rule_audit_required_columns_are_not_nullable():
    table = DataQualityRuleAuditEvent.__table__

    for column in table.columns:
        assert column.nullable is False, column.name


def test_rule_audit_version_foreign_key_is_composite():
    table = DataQualityRuleAuditEvent.__table__

    constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]

    composite = next(
        constraint
        for constraint in constraints
        if constraint.name == "fk_dq_rule_audit_version_identity"
    )

    assert {column.name for column in composite.columns} == {
        "rule_id",
        "version_id",
    }
    assert {
        element.target_fullname
        for element in composite.elements
    } == {
        "data_quality_rule_versions.rule_id",
        "data_quality_rule_versions.id",
    }


def test_rule_audit_event_types_are_restricted():
    table = DataQualityRuleAuditEvent.__table__

    constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    ]

    event_constraint = next(
        constraint
        for constraint in constraints
        if constraint.name == "ck_dq_rule_audit_event_type"
    )

    sql = str(event_constraint.sqltext)

    assert "version.approved" in sql
    assert "version.activated" in sql
