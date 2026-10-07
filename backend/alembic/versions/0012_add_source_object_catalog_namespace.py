"""Add catalog namespace to source objects.

Revision ID: 0012
Revises: 0011
"""

from alembic import op
import sqlalchemy as sa


revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "source_objects",
        sa.Column(
            "catalog_name",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.drop_constraint(
        "uq_source_objects_source_name",
        "source_objects",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_source_objects_namespace_name",
        "source_objects",
        [
            "data_source_id",
            "catalog_name",
            "schema_name",
            "object_name",
        ],
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_source_objects_namespace_name",
        "source_objects",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_source_objects_source_name",
        "source_objects",
        ["data_source_id", "object_name"],
    )

    op.drop_column("source_objects", "catalog_name")
