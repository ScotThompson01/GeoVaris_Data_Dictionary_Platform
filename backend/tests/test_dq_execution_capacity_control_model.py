"""Regression tests for Phase 5E capacity-control schema metadata."""

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.models.data_quality_execution_capacity_control import (
    DataQualityExecutionCapacityControl,
)


def test_capacity_control_required_columns():
    table = DataQualityExecutionCapacityControl.__table__

    assert table.c.scope_type.nullable is False
    assert table.c.max_concurrent.nullable is False
    assert table.c.data_source_id.nullable is True


def test_capacity_control_check_constraints():
    table = DataQualityExecutionCapacityControl.__table__

    names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert {
        "ck_dq_capacity_control_scope",
        "ck_dq_capacity_control_positive_limit",
        "ck_dq_capacity_control_source_scope",
    }.issubset(names)


def test_capacity_control_source_uniqueness():
    table = DataQualityExecutionCapacityControl.__table__

    assert any(
        isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_dq_capacity_control_data_source"
        and [column.name for column in constraint.columns] == ["data_source_id"]
        for constraint in table.constraints
    )


def test_single_installation_partial_unique_index():
    table = DataQualityExecutionCapacityControl.__table__

    index = next(
        index
        for index in table.indexes
        if index.name == "uq_dq_capacity_single_installation"
    )

    assert index.unique is True
    assert [column.name for column in index.columns] == ["scope_type"]
    assert "scope_type = 'installation'" in str(
        index.dialect_options["postgresql"]["where"]
    )


def test_capacity_control_source_deletion_restricted():
    table = DataQualityExecutionCapacityControl.__table__

    foreign_keys = list(table.c.data_source_id.foreign_keys)

    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "data_sources.id"
    assert foreign_keys[0].ondelete == "RESTRICT"
