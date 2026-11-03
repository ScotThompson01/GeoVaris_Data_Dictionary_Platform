"""Persistent ownership of admitted Data Quality source workloads.

Schema proposal only. Does not authorize source execution.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DataQualityWorkloadOwnership(Base):
    __tablename__ = "data_quality_workload_ownership"

    __table_args__ = (
        UniqueConstraint(
            "id",
            "data_source_id",
            name="uq_dq_workload_id_source",
        ),
        ForeignKeyConstraint(
            ["rule_id", "data_field_id"],
            ["data_quality_rules.id", "data_quality_rules.data_field_id"],
            name="fk_dq_workload_rule_field_identity",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["data_field_id", "source_object_id"],
            ["data_fields.id", "data_fields.source_object_id"],
            name="fk_dq_workload_field_object_identity",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_object_id", "data_source_id"],
            ["source_objects.id", "source_objects.data_source_id"],
            name="fk_dq_workload_source_object_identity",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["data_source_id", "project_id"],
            ["data_sources.id", "data_sources.project_id"],
            name="fk_dq_workload_data_source_identity",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["execution_id", "project_id", "rule_id"],
            [
                "data_quality_rule_executions.id",
                "data_quality_rule_executions.project_id",
                "data_quality_rule_executions.rule_id",
            ],
            name="fk_dq_workload_execution_identity",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "("
            "ownership_state = 'released' "
            "AND released_at IS NOT NULL "
            "AND NULLIF(BTRIM(release_actor), '') IS NOT NULL "
            "AND NULLIF(BTRIM(release_reason), '') IS NOT NULL "
            "AND NULLIF(BTRIM(release_evidence_reference), '') IS NOT NULL"
            ") OR ("
            "ownership_state IN ('reserved', 'unresolved') "
            "AND released_at IS NULL "
            "AND release_actor IS NULL "
            "AND release_reason IS NULL "
            "AND release_evidence_reference IS NULL"
            ")",
            name="ck_dq_workload_release_audit",
        ),
        CheckConstraint(
            "scope_type = 'full_object'",
            name="ck_dq_workload_scope",
        ),
        CheckConstraint(
            "ownership_state IN ('reserved', 'unresolved', 'released')",
            name="ck_dq_workload_state",
        ),
        Index(
            "uq_dq_active_workload_identity",
            "rule_id",
            "source_object_id",
            "scope_type",
            unique=True,
            postgresql_where=text(
                "ownership_state IN ('reserved', 'unresolved')"
            ),
        ),
        Index(
            "ix_dq_workload_data_source_state",
            "data_source_id",
            "ownership_state",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_quality_rules.id", ondelete="RESTRICT"),
        nullable=False,
    )

    data_field_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    source_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_objects.id", ondelete="RESTRICT"),
        nullable=False,
    )

    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )

    scope_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="full_object",
        server_default="full_object",
    )

    ownership_state: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="reserved",
        server_default="reserved",
    )

    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    release_actor: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    release_reason: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    release_evidence_reference: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
