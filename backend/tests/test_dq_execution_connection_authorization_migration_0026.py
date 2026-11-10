"""Static contracts for additive authorization migration 0026.

These tests do not open a database or apply migrations.
"""

import ast
from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0026_create_dq_execution_connection_authorization.py"
)

TABLE = "data_quality_execution_connection_authorizations"
UNIQUE = "uq_dq_workload_execution_project_source"


def _source():
    return MIGRATION.read_text(encoding="utf-8")


def test_revision_follows_phase5e_protection():
    tree = ast.parse(_source())
    values = {}

    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            if isinstance(node, ast.Assign):
                names = [
                    target.id
                    for target in node.targets
                    if isinstance(target, ast.Name)
                ]
            else:
                names = (
                    [node.target.id]
                    if isinstance(node.target, ast.Name)
                    else []
                )

            for name in names:
                if name in ("revision", "down_revision"):
                    values[name] = ast.literal_eval(node.value)

    assert values["revision"] == "0026"
    assert values["down_revision"] == "0025"


def test_composite_unique_identity_precedes_authorization_table():
    text = _source()

    assert UNIQUE in text
    assert text.index("op.create_unique_constraint(") < (
        text.index("op.create_table(")
    )
    assert "execution_id" in text
    assert "project_id" in text
    assert "data_source_id" in text


def test_authorization_table_and_required_safeguards():
    text = _source()

    assert f'op.create_table(\n        "{TABLE}"' in text

    for column in (
        "execution_id",
        "project_id",
        "data_source_id",
        "connection_revision",
        "authorized_host",
        "authorized_port",
        "authorized_database",
        "authorized_ip",
        "authorized_at",
    ):
        assert f'"{column}"' in text

    for constraint in (
        "fk_dq_connection_auth_execution_source",
        "fk_dq_connection_auth_registered_source",
        "ck_dq_connection_auth_positive_revision",
        "ck_dq_connection_auth_valid_port",
    ):
        assert constraint in text

    assert "ondelete=\"RESTRICT\"" in text


def test_downgrade_reverses_dependencies():
    text = _source()
    downgrade = text.split("def downgrade()", 1)[1]

    table_drop = downgrade.index("op.drop_table(")
    unique_drop = downgrade.index("op.drop_constraint(")

    assert table_drop < unique_drop
    assert TABLE in downgrade
    assert UNIQUE in downgrade


def test_migration_uses_explicit_ddl_only():
    text = _source()

    for forbidden in (
        "Base.metadata.create_all",
        "Base.metadata.drop_all",
        "from app.models",
        "autogenerate",
    ):
        assert forbidden not in text
