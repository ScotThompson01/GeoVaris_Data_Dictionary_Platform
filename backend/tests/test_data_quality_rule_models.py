"""Metadata tests for Phase 5 Data Quality persistence models."""

from sqlalchemy import CheckConstraint, UniqueConstraint

import app.db.base  # noqa: F401 - registers all application models
from app.db.session import Base


def test_data_quality_tables_are_registered():
    assert "data_quality_rules" in Base.metadata.tables
    assert "data_quality_rule_versions" in Base.metadata.tables


def test_rule_identity_has_required_columns():
    table = Base.metadata.tables["data_quality_rules"]

    assert {
        "id",
        "data_field_id",
        "rule_name",
        "status",
        "created_at",
        "updated_at",
    }.issubset(table.columns.keys())


def test_rule_field_reference_restricts_deletion():
    table = Base.metadata.tables["data_quality_rules"]

    assert any(
        fk.target_fullname == "data_fields.id"
        and fk.ondelete == "RESTRICT"
        for fk in table.foreign_keys
    )


def test_version_has_required_columns():
    table = Base.metadata.tables["data_quality_rule_versions"]

    assert {
        "id",
        "rule_id",
        "version_number",
        "rule_type",
        "quality_dimension",
        "min_value",
        "max_value",
        "null_allowed",
        "status",
        "created_at",
    }.issubset(table.columns.keys())


def test_version_rule_reference_restricts_deletion():
    table = Base.metadata.tables["data_quality_rule_versions"]

    assert any(
        fk.target_fullname == "data_quality_rules.id"
        and fk.ondelete == "RESTRICT"
        for fk in table.foreign_keys
    )


def test_rule_version_number_is_unique():
    table = Base.metadata.tables["data_quality_rule_versions"]

    assert any(
        isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_data_quality_rule_version_number"
        and {column.name for column in constraint.columns}
        == {"rule_id", "version_number"}
        for constraint in table.constraints
    )


def test_version_check_constraints_are_present():
    table = Base.metadata.tables["data_quality_rule_versions"]

    constraint_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert {
        "ck_data_quality_rule_version_positive",
        "ck_data_quality_rule_version_range",
        "ck_data_quality_rule_version_status",
    }.issubset(constraint_names)


def test_null_allowed_is_required_with_default():
    table = Base.metadata.tables["data_quality_rule_versions"]
    column = table.columns["null_allowed"]

    assert column.nullable is False
    assert column.server_default is not None


def test_rule_lifecycle_constraint_is_present():
    table = Base.metadata.tables["data_quality_rules"]

    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_data_quality_rule_status"
        and "'draft'" in str(constraint.sqltext)
        and "'active'" in str(constraint.sqltext)
        and "'retired'" in str(constraint.sqltext)
        for constraint in table.constraints
    )


def test_version_parent_identity_is_unique():
    table = Base.metadata.tables["data_quality_rule_versions"]

    assert any(
        isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_data_quality_rule_version_parent_identity"
        and {column.name for column in constraint.columns}
        == {"rule_id", "id"}
        for constraint in table.constraints
    )


def test_active_version_reference_is_scoped_to_parent_rule():
    table = Base.metadata.tables["data_quality_rules"]

    assert "active_version_id" in table.columns
    assert table.columns["active_version_id"].nullable is True

    constraints = [
        constraint
        for constraint in table.foreign_key_constraints
        if constraint.name == "fk_data_quality_rule_active_version"
    ]

    assert len(constraints) == 1

    constraint = constraints[0]
    assert constraint.ondelete == "RESTRICT"
    assert {
        (element.parent.name, element.target_fullname)
        for element in constraint.elements
    } == {
        ("id", "data_quality_rule_versions.rule_id"),
        ("active_version_id", "data_quality_rule_versions.id"),
    }


def test_version_rule_type_and_dimension_constraints():
    table = Base.metadata.tables["data_quality_rule_versions"]

    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "ck_data_quality_rule_version_type" in constraints
    assert "rule_type = 'range'" in constraints[
        "ck_data_quality_rule_version_type"
    ]

    assert "ck_data_quality_rule_version_dimension" in constraints
    assert "quality_dimension = 'validity'" in constraints[
        "ck_data_quality_rule_version_dimension"
    ]
