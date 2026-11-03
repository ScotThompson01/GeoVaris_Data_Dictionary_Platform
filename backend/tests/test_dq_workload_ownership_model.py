"""Regression tests for Phase 5E workload ownership schema metadata."""

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint

from app.models.data_quality_rule_execution import DataQualityRuleExecution
from app.models.data_quality_rule import DataQualityRule
from app.models.data_field import DataField
from app.models.source_object import SourceObject
from app.models.data_source import DataSource
from app.models.data_quality_workload_ownership import DataQualityWorkloadOwnership


def test_supporting_composite_unique_constraints():
    expected = [
        (DataQualityRuleExecution, "uq_dq_execution_project_rule_identity",
         ["id", "project_id", "rule_id"]),
        (DataQualityRule, "uq_dq_rule_field_identity",
         ["id", "data_field_id"]),
        (DataField, "uq_data_field_object_identity",
         ["id", "source_object_id"]),
        (SourceObject, "uq_source_object_source_identity",
         ["id", "data_source_id"]),
        (DataSource, "uq_data_source_project_identity",
         ["id", "project_id"]),
    ]

    for model, name, columns in expected:
        assert any(
            isinstance(constraint, UniqueConstraint)
            and constraint.name == name
            and [column.name for column in constraint.columns] == columns
            for constraint in model.__table__.constraints
        ), name


def test_ownership_composite_foreign_keys():
    expected = {
        "fk_dq_workload_execution_identity": (
            ["execution_id", "project_id", "rule_id"],
            ["data_quality_rule_executions.id",
             "data_quality_rule_executions.project_id",
             "data_quality_rule_executions.rule_id"],
        ),
        "fk_dq_workload_rule_field_identity": (
            ["rule_id", "data_field_id"],
            ["data_quality_rules.id", "data_quality_rules.data_field_id"],
        ),
        "fk_dq_workload_field_object_identity": (
            ["data_field_id", "source_object_id"],
            ["data_fields.id", "data_fields.source_object_id"],
        ),
        "fk_dq_workload_source_object_identity": (
            ["source_object_id", "data_source_id"],
            ["source_objects.id", "source_objects.data_source_id"],
        ),
        "fk_dq_workload_data_source_identity": (
            ["data_source_id", "project_id"],
            ["data_sources.id", "data_sources.project_id"],
        ),
    }

    constraints = {
        constraint.name: constraint
        for constraint in DataQualityWorkloadOwnership.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }

    for name, (columns, targets) in expected.items():
        constraint = constraints[name]
        assert [column.name for column in constraint.columns] == columns
        assert [element.target_fullname for element in constraint.elements] == targets
        assert constraint.ondelete == "RESTRICT"


def test_active_ownership_partial_unique_index():
    indexes = {
        index.name: index
        for index in DataQualityWorkloadOwnership.__table__.indexes
    }

    index = indexes["uq_dq_active_workload_identity"]

    assert index.unique
    assert [column.name for column in index.columns] == [
        "rule_id",
        "source_object_id",
        "scope_type",
    ]

    predicate = str(index.dialect_options["postgresql"]["where"])
    assert "'reserved'" in predicate
    assert "'unresolved'" in predicate


def test_one_ownership_record_per_execution():
    column = DataQualityWorkloadOwnership.__table__.c.execution_id
    assert column.nullable is False
    assert column.unique is True
