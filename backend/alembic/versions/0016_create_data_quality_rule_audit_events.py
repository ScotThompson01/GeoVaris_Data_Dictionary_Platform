"""Create audit history for Data Quality rule lifecycle changes.

Revision ID: 0016
Revises: 0015
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0016"
down_revision: Union[str, Sequence[str], None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_quality_rule_audit_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=False),
        sa.Column("rule_id", sa.UUID(), nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("old_status", sa.String(length=50), nullable=False),
        sa.Column("new_status", sa.String(length=50), nullable=False),
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
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rule_id", "version_id"],
            [
                "data_quality_rule_versions.rule_id",
                "data_quality_rule_versions.id",
            ],
            name="fk_dq_rule_audit_version_identity",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "event_type IN ('version.approved', 'version.activated')",
            name="ck_dq_rule_audit_event_type",
        ),
    )

    op.create_index(
        "ix_dq_rule_audit_project_id",
        "data_quality_rule_audit_events",
        ["project_id"],
    )
    op.create_index(
        "ix_dq_rule_audit_actor_user_id",
        "data_quality_rule_audit_events",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_dq_rule_audit_rule_id",
        "data_quality_rule_audit_events",
        ["rule_id"],
    )
    op.create_index(
        "ix_dq_rule_audit_created_at",
        "data_quality_rule_audit_events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dq_rule_audit_created_at",
        table_name="data_quality_rule_audit_events",
    )
    op.drop_index(
        "ix_dq_rule_audit_rule_id",
        table_name="data_quality_rule_audit_events",
    )
    op.drop_index(
        "ix_dq_rule_audit_actor_user_id",
        table_name="data_quality_rule_audit_events",
    )
    op.drop_index(
        "ix_dq_rule_audit_project_id",
        table_name="data_quality_rule_audit_events",
    )
    op.drop_table("data_quality_rule_audit_events")
