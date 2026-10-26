"""Create Phase 5 Data Quality rule and version tables.

Revision ID: 0013
Revises: e7295f542f78
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0013"
down_revision: Union[str, Sequence[str], None] = "e7295f542f78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_quality_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("data_field_id", sa.UUID(), nullable=False),
        sa.Column("active_version_id", sa.UUID(), nullable=True),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["data_field_id"],
            ["data_fields.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'retired')",
            name="ck_data_quality_rule_status",
        ),
    )
    op.create_index(
        "ix_data_quality_rules_data_field_id",
        "data_quality_rules",
        ["data_field_id"],
    )

    op.create_table(
        "data_quality_rule_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("rule_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "rule_type",
            sa.String(length=50),
            server_default="range",
            nullable=False,
        ),
        sa.Column(
            "quality_dimension",
            sa.String(length=50),
            server_default="validity",
            nullable=False,
        ),
        sa.Column(
            "min_value",
            sa.Numeric(precision=24, scale=10),
            nullable=False,
        ),
        sa.Column(
            "max_value",
            sa.Numeric(precision=24, scale=10),
            nullable=False,
        ),
        sa.Column(
            "null_allowed",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["data_quality_rules.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "rule_id",
            "version_number",
            name="uq_data_quality_rule_version_number",
        ),
        sa.UniqueConstraint(
            "rule_id",
            "id",
            name="uq_data_quality_rule_version_parent_identity",
        ),
        sa.CheckConstraint(
            "version_number >= 1",
            name="ck_data_quality_rule_version_positive",
        ),
        sa.CheckConstraint(
            "min_value <= max_value",
            name="ck_data_quality_rule_version_range",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'retired')",
            name="ck_data_quality_rule_version_status",
        ),
        sa.CheckConstraint(
            "rule_type = 'range'",
            name="ck_data_quality_rule_version_type",
        ),
        sa.CheckConstraint(
            "quality_dimension = 'validity'",
            name="ck_data_quality_rule_version_dimension",
        ),
    )
    op.create_index(
        "ix_data_quality_rule_versions_rule_id",
        "data_quality_rule_versions",
        ["rule_id"],
    )

    # Add the circular reference only after both tables exist.
    op.create_foreign_key(
        "fk_data_quality_rule_active_version",
        "data_quality_rules",
        "data_quality_rule_versions",
        ["id", "active_version_id"],
        ["rule_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_data_quality_rule_active_version",
        "data_quality_rules",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_data_quality_rule_versions_rule_id",
        table_name="data_quality_rule_versions",
    )
    op.drop_table("data_quality_rule_versions")
    op.drop_index(
        "ix_data_quality_rules_data_field_id",
        table_name="data_quality_rules",
    )
    op.drop_table("data_quality_rules")
