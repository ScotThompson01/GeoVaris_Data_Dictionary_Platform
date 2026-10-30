"""Add explicit project-level data source connection management permission.

Revision ID: 0021
Revises: 0020
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0021"
down_revision: Union[str, Sequence[str], None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "project_access",
        sa.Column(
            "can_manage_data_source_connections",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "project_access",
        "can_manage_data_source_connections",
    )