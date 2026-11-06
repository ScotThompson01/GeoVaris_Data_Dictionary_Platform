"""Static structure checks for unapplied Phase 5E migration 0025.

No migrations are executed and no database connection is made.
"""

import ast
from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0025_create_phase5e_execution_protection.py"
)

TABLES = [
    "data_quality_workload_resolution_grants",
    "data_quality_execution_capacity_controls",
    "data_quality_workload_ownership",
    "data_quality_execution_capacity_reservations",
    "data_quality_workload_release_evidence",
]

PREREQUISITES = [
    "uq_data_source_project_identity",
    "uq_source_object_source_identity",
    "uq_data_field_object_identity",
    "uq_dq_rule_field_identity",
    "uq_dq_execution_project_rule_identity",
]


def source():
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_revision_follows_0024():
    tree = ast.parse(source())
    assignments = {}

    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = ast.literal_eval(statement.value)

    assert assignments["revision"] == "0025"
    assert assignments["down_revision"] == "0024"


def test_prerequisite_constraints_precede_new_tables():
    text = source()
    first_table = text.index("CREATE TABLE ")

    for name in PREREQUISITES:
        assert text.index(f"op.create_unique_constraint('{name}'") < first_table


def test_all_five_tables_are_created_in_dependency_order():
    text = source()
    positions = [text.index(f"CREATE TABLE {name} ") for name in TABLES]

    assert positions == sorted(positions)


def test_new_tables_have_matching_downgrade_operations():
    text = source()
    downgrade = text.split("def downgrade() -> None:", 1)[1]

    positions = [
        downgrade.index(f"op.drop_table('{name}')")
        for name in reversed(TABLES)
    ]

    assert positions == sorted(positions)


def test_prerequisite_constraints_have_reverse_downgrade():
    text = source()
    downgrade = text.split("def downgrade() -> None:", 1)[1]

    positions = [
        downgrade.index(f"op.drop_constraint('{name}'")
        for name in reversed(PREREQUISITES)
    ]

    assert positions == sorted(positions)


def test_source_reservation_null_guard_is_present():
    assert (
        "reservation_scope = 'source' "
        "AND data_source_id IS NOT NULL "
        "AND data_source_id = ownership_data_source_id"
    ) in source()


def test_unique_partial_indexes_are_defined():
    text = source()

    assert "CREATE UNIQUE INDEX uq_dq_capacity_single_installation" in text
    assert "CREATE UNIQUE INDEX uq_dq_active_workload_identity" in text


def test_migration_uses_static_ddl():
    text = source()

    assert "Base.metadata.create_all" not in text
    assert "Base.metadata.drop_all" not in text
    assert "from app.models" not in text
    assert "autogenerate" not in text
