"""Add explicit project-level Data Quality rule approval permission.

Revision ID: 0018
Revises: 0017
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0018"
down_revision: Union[str, Sequence[str], None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "project_access",
        sa.Column(
            "can_approve_dq_rules",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("project_access", "can_approve_dq_rules")
