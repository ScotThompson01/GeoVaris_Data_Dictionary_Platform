"""create data fields

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_fields",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "source_object_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "field_name",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "ordinal_position",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "native_data_type",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "normalized_data_type",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "max_length",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "numeric_precision",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "numeric_scale",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "is_nullable",
            sa.Boolean(),
            nullable=True,
        ),
        sa.Column(
            "is_primary_key",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_unique",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "default_value",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "source_comment",
            sa.Text(),
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
            ["source_object_id"],
            ["source_objects.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_object_id",
            "field_name",
            name="uq_data_fields_object_name",
        ),
    )

    op.create_index(
        "ix_data_fields_source_object_id",
        "data_fields",
        ["source_object_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_data_fields_source_object_id",
        table_name="data_fields",
    )

    op.drop_table("data_fields")