"""Extend Data Quality execution lifecycle states.

Revision ID: 0024
Revises: 0023

Preserves existing execution records and aggregate history.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0024"
down_revision: Union[str, Sequence[str], None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_STATUS = "status IN ('succeeded', 'failed')"

NEW_STATUS = (
    "status IN ("
    "'pending', 'running', 'succeeded', 'failed', "
    "'incomplete', 'status_uncertain', 'cancelled'"
    ")"
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_dq_execution_status",
        "data_quality_rule_executions",
        type_="check",
    )

    op.create_check_constraint(
        "ck_dq_execution_status",
        "data_quality_rule_executions",
        NEW_STATUS,
    )

    op.alter_column(
        "data_quality_rule_executions",
        "started_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )


def downgrade() -> None:
    # Reject unsafe downgrades without modifying existing records.
    connection = op.get_bind()

    incompatible_count = connection.scalar(
        sa.text("""
            SELECT COUNT(*)
            FROM data_quality_rule_executions
            WHERE status NOT IN ('succeeded', 'failed')
               OR started_at IS NULL
        """)
    )

    if incompatible_count:
        raise RuntimeError(
            "Cannot downgrade execution lifecycle while newer "
            "statuses or NULL start timestamps exist."
        )

    op.alter_column(
        "data_quality_rule_executions",
        "started_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )

    op.drop_constraint(
        "ck_dq_execution_status",
        "data_quality_rule_executions",
        type_="check",
    )

    op.create_check_constraint(
        "ck_dq_execution_status",
        "data_quality_rule_executions",
        OLD_STATUS,
    )
