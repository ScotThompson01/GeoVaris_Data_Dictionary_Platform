"""Create non-secret PostgreSQL connection identities.

Revision ID: 0022
Revises: 0021
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0022"
down_revision: Union[str, Sequence[str], None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "postgresql_connection_identities",
        sa.Column("data_source_id", sa.UUID(), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("database_name", sa.String(length=255), nullable=False),
        sa.Column(
            "is_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("data_source_id"),
        sa.ForeignKeyConstraint(
            ["data_source_id"],
            ["data_sources.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "port BETWEEN 1 AND 65535",
            name="ck_postgresql_connection_identity_port",
        ),
        sa.CheckConstraint(
            "NOT is_verified OR verified_at IS NOT NULL",
            name="ck_postgresql_connection_identity_verified_at",
        ),
    )


def downgrade() -> None:
    op.drop_table("postgresql_connection_identities")