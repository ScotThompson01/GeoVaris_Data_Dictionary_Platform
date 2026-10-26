"""Track the authenticated creator of Data Quality rule versions.

Revision ID: 0017
Revises: 0016
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0017"
down_revision: Union[str, Sequence[str], None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "data_quality_rule_versions",
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_dq_rule_version_created_by_user",
        "data_quality_rule_versions",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_dq_rule_version_created_by_user",
        "data_quality_rule_versions",
        type_="foreignkey",
    )
    op.drop_column(
        "data_quality_rule_versions",
        "created_by_user_id",
    )
