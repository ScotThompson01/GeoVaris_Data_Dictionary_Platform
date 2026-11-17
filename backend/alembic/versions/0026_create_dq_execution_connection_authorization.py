"""Create execution-bound PostgreSQL authorization evidence.

Revision ID: 0026
Revises: 0025

This migration creates metadata-only authorization evidence.
It does not authorize or execute source measurements.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_dq_workload_execution_project_source",
        "data_quality_workload_ownership",
        ["execution_id", "project_id", "data_source_id"],
    )

    op.create_table(
        "data_quality_execution_connection_authorizations",
        sa.Column(
            "execution_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "data_source_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "connection_revision",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "authorized_host",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "authorized_port",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "authorized_database",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "authorized_ip",
            sa.String(length=45),
            nullable=False,
        ),
        sa.Column(
            "authorized_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "execution_id",
        ),
        sa.ForeignKeyConstraint(
            ["execution_id", "project_id", "data_source_id"],
            [
                "data_quality_workload_ownership.execution_id",
                "data_quality_workload_ownership.project_id",
                "data_quality_workload_ownership.data_source_id",
            ],
            name="fk_dq_connection_auth_execution_source",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["data_source_id"],
            ["postgresql_connection_identities.data_source_id"],
            name="fk_dq_connection_auth_registered_source",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "connection_revision >= 1",
            name="ck_dq_connection_auth_positive_revision",
        ),
        sa.CheckConstraint(
            "authorized_port BETWEEN 1 AND 65535",
            name="ck_dq_connection_auth_valid_port",
        ),
    )


def downgrade() -> None:
    op.drop_table(
        "data_quality_execution_connection_authorizations"
    )

    op.drop_constraint(
        "uq_dq_workload_execution_project_source",
        "data_quality_workload_ownership",
        type_="unique",
    )
