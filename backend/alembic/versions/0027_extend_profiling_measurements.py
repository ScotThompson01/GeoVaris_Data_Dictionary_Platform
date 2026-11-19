"""Extend profiling measurements for relational databases.

Revision ID: 0027
Revises: 0026
"""

from alembic import op
import sqlalchemy as sa


revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in ("row_count", "null_count"):
        op.alter_column(
            "profiling_results",
            column,
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=False,
        )

    op.alter_column(
        "profiling_results",
        "distinct_count",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        nullable=True,
    )

    for column in ("null_percentage", "distinct_percentage"):
        op.alter_column(
            "profiling_results",
            column,
            existing_type=sa.Numeric(7, 4),
            existing_nullable=False,
            nullable=True,
        )


def downgrade() -> None:
    # Refuse a downgrade that would lose measurement information.
    connection = op.get_bind()

    incompatible = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM profiling_results
                WHERE row_count > 2147483647
                   OR null_count > 2147483647
                   OR distinct_count > 2147483647
                   OR distinct_count IS NULL
                   OR null_percentage IS NULL
                   OR distinct_percentage IS NULL
            )
            """
        )
    ).scalar_one()

    if incompatible:
        raise RuntimeError(
            "Downgrade would lose profiling measurement information."
        )

    for column in ("null_percentage", "distinct_percentage"):
        op.alter_column(
            "profiling_results",
            column,
            existing_type=sa.Numeric(7, 4),
            existing_nullable=True,
            nullable=False,
        )

    op.alter_column(
        "profiling_results",
        "distinct_count",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
        nullable=False,
    )

    for column in ("row_count", "null_count"):
        op.alter_column(
            "profiling_results",
            column,
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=False,
        )
