"""create source objects

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_objects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "data_source_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "object_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "object_name",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "schema_name",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "native_name",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "row_count",
            sa.Integer(),
            nullable=True,
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
            ["data_source_id"],
            ["data_sources.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "data_source_id",
            "object_name",
            name="uq_source_objects_source_name",
        ),
    )

    op.create_index(
        "ix_source_objects_data_source_id",
        "source_objects",
        ["data_source_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_source_objects_data_source_id",
        table_name="source_objects",
    )

    op.drop_table("source_objects")