"""Create Data Quality rule execution history.

Revision ID: 0020
Revises: 0019
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0020"
down_revision: Union[str, Sequence[str], None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_quality_rule_executions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=False),
        sa.Column("rule_id", sa.UUID(), nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("total_count", sa.BigInteger(), nullable=True),
        sa.Column("passing_count", sa.BigInteger(), nullable=True),
        sa.Column("violation_count", sa.BigInteger(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_dq_execution_project",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_dq_execution_actor_user",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rule_id", "version_id"],
            [
                "data_quality_rule_versions.rule_id",
                "data_quality_rule_versions.id",
            ],
            name="fk_dq_execution_rule_version_identity",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('succeeded', 'failed')",
            name="ck_dq_execution_status",
        ),
        sa.CheckConstraint(
            "total_count IS NULL OR total_count >= 0",
            name="ck_dq_execution_total_nonnegative",
        ),
        sa.CheckConstraint(
            "passing_count IS NULL OR passing_count >= 0",
            name="ck_dq_execution_passing_nonnegative",
        ),
        sa.CheckConstraint(
            "violation_count IS NULL OR violation_count >= 0",
            name="ck_dq_execution_violations_nonnegative",
        ),
        sa.CheckConstraint(
            """
            status != 'succeeded'
            OR (
                total_count IS NOT NULL
                AND passing_count IS NOT NULL
                AND violation_count IS NOT NULL
                AND total_count = passing_count + violation_count
            )
            """,
            name="ck_dq_execution_success_counts",
        ),
    )

    op.create_index(
        "ix_dq_execution_project_id",
        "data_quality_rule_executions",
        ["project_id"],
    )
    op.create_index(
        "ix_dq_execution_actor_user_id",
        "data_quality_rule_executions",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_dq_execution_rule_id",
        "data_quality_rule_executions",
        ["rule_id"],
    )
    op.create_index(
        "ix_dq_execution_created_at",
        "data_quality_rule_executions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dq_execution_created_at",
        table_name="data_quality_rule_executions",
    )
    op.drop_index(
        "ix_dq_execution_rule_id",
        table_name="data_quality_rule_executions",
    )
    op.drop_index(
        "ix_dq_execution_actor_user_id",
        table_name="data_quality_rule_executions",
    )
    op.drop_index(
        "ix_dq_execution_project_id",
        table_name="data_quality_rule_executions",
    )
    op.drop_table("data_quality_rule_executions")
