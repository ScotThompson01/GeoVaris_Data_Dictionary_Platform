"""Add a revision counter to registered PostgreSQL connection identities.

Revision ID: 0023
Revises: 0022
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0023"
down_revision: Union[str, Sequence[str], None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "postgresql_connection_identities",
        sa.Column(
            "connection_revision",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )

    op.create_check_constraint(
        "ck_postgresql_connection_identity_revision_positive",
        "postgresql_connection_identities",
        "connection_revision >= 1",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_postgresql_connection_identity_revision_positive",
        "postgresql_connection_identities",
        type_="check",
    )

    op.drop_column(
        "postgresql_connection_identities",
        "connection_revision",
    )
