"""create data sources

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_sources",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "name",
            sa.String(length=200),
            nullable=False,
        ),

        sa.Column(
            "source_type",
            sa.String(length=50),
            nullable=False,
        ),

        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "connection_mode",
            sa.String(length=50),
            nullable=False,
        ),

        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "project_id",
            "name",
            name="uq_data_sources_project_name",
        ),
    )

    op.create_index(
        "ix_data_sources_project_id",
        "data_sources",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_data_sources_project_id",
        table_name="data_sources",
    )

    op.drop_table(
        "data_sources",
    )