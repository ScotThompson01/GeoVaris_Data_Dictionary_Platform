"""Offline prerequisites for the proposed Phase 5E migration.

These tests do not connect to or modify a database.
They do not prove that historical database constraints exist.
"""

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db import base  # noqa: F401
from app.db.session import Base


PREREQUISITES = {
    "data_sources": ("id", "project_id"),
    "source_objects": ("id", "data_source_id"),
    "data_fields": ("id", "source_object_id"),
    "data_quality_rules": ("id", "data_field_id"),
    "data_quality_rule_executions": (
        "id", "project_id", "rule_id"
    ),
}

NEW_TABLES = {
    "data_quality_execution_capacity_controls",
    "data_quality_workload_resolution_grants",
    "data_quality_workload_ownership",
    "data_quality_execution_capacity_reservations",
    "data_quality_workload_release_evidence",
}


def test_existing_models_define_required_unique_identities():
    for name, columns in PREREQUISITES.items():
        table = Base.metadata.tables[name]
        assert any(
            isinstance(constraint, UniqueConstraint)
            and tuple(column.name for column in constraint.columns) == columns
            for constraint in table.constraints
        ), name


def test_new_tables_compile_for_postgresql():
    dialect = postgresql.dialect()

    for name in NEW_TABLES:
        table = Base.metadata.tables[name]
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert ddl.lstrip().startswith("CREATE TABLE"), name

        for index in table.indexes:
            assert str(
                CreateIndex(index).compile(dialect=dialect)
            ).lstrip().startswith("CREATE"), index.name


def test_new_table_dependencies_are_ordered():
    ordered = [
        table.name
        for table in Base.metadata.sorted_tables
        if table.name in NEW_TABLES
    ]

    positions = {name: index for index, name in enumerate(ordered)}

    assert set(ordered) == NEW_TABLES
    assert positions["data_quality_execution_capacity_controls"] < (
        positions["data_quality_execution_capacity_reservations"]
    )
    assert positions["data_quality_workload_ownership"] < (
        positions["data_quality_execution_capacity_reservations"]
    )
    assert positions["data_quality_workload_ownership"] < (
        positions["data_quality_workload_release_evidence"]
    )
    assert positions["data_quality_workload_resolution_grants"] < (
        positions["data_quality_workload_release_evidence"]
    )


def test_reservation_ownership_foreign_key_is_nonnullable():
    table = Base.metadata.tables[
        "data_quality_execution_capacity_reservations"
    ]
    matches = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and constraint.name == "fk_dq_reservation_ownership_source"
    ]

    assert len(matches) == 1
    assert all(not column.nullable for column in matches[0].columns)


def test_new_tables_have_no_implicit_cascade_delete_foreign_keys():
    for name in NEW_TABLES:
        table = Base.metadata.tables[name]

        for constraint in table.constraints:
            if isinstance(constraint, ForeignKeyConstraint):
                assert constraint.ondelete != "CASCADE", (
                    name, constraint.name
                )
