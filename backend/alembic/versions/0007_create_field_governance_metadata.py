"""create field governance metadata

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "field_governance_metadata",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "data_field_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "business_name",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "business_definition",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "department",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "data_owner",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "data_steward",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "business_process",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "system_of_record",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "is_cde",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),

        sa.Column(
            "classification",
            sa.String(length=100),
            nullable=True,
        ),

        sa.Column(
            "approval_status",
            sa.String(length=50),
            server_default="draft",
            nullable=False,
        ),

        sa.Column(
            "notes",
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
            ["data_field_id"],
            ["data_fields.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "data_field_id",
            name="uq_field_governance_metadata_data_field_id",
        ),
    )

    op.create_index(
        "ix_field_governance_metadata_data_field_id",
        "field_governance_metadata",
        ["data_field_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_field_governance_metadata_data_field_id",
        table_name="field_governance_metadata",
    )

    op.drop_table(
        "field_governance_metadata"
    )