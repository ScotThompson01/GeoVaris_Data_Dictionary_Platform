"""create profiling results

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiling_results",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "data_field_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "row_count",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "null_count",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "null_percentage",
            sa.Numeric(7, 4),
            nullable=False,
        ),

        sa.Column(
            "distinct_count",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "distinct_percentage",
            sa.Numeric(7, 4),
            nullable=False,
        ),

        sa.Column(
            "minimum_value",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "maximum_value",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "minimum_length",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "maximum_length",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["scan_id"],
            ["scans.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["data_field_id"],
            ["data_fields.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "scan_id",
            "data_field_id",
            name="uq_profiling_results_scan_field",
        ),
    )

    op.create_index(
        "ix_profiling_results_scan_id",
        "profiling_results",
        ["scan_id"],
        unique=False,
    )

    op.create_index(
        "ix_profiling_results_data_field_id",
        "profiling_results",
        ["data_field_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_profiling_results_data_field_id",
        table_name="profiling_results",
    )

    op.drop_index(
        "ix_profiling_results_scan_id",
        table_name="profiling_results",
    )

    op.drop_table("profiling_results")