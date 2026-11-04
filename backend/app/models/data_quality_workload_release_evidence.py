"""Proposed durable release evidence for Phase 5E.

Metadata and evidence references only; no source data or credentials.
A recorded or confirmed row is not independently trusted until an
authorized verification workflow establishes its validity.
No migration or runtime release is authorized by this model.
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
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DataQualityWorkloadReleaseEvidence(Base):
    __tablename__ = "data_quality_workload_release_evidence"

    __table_args__ = (
        ForeignKeyConstraint(
            ["ownership_id", "project_id", "data_source_id"],
            [
                "data_quality_workload_ownership.id",
                "data_quality_workload_ownership.project_id",
                "data_quality_workload_ownership.data_source_id",
            ],
            name="fk_dq_release_evidence_workload_identity",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["resolution_grant_id", "project_id", "actor_user_id"],
            [
                "data_quality_workload_resolution_grants.id",
                "data_quality_workload_resolution_grants.project_id",
                "data_quality_workload_resolution_grants.user_id",
            ],
            name="fk_dq_release_evidence_resolution_grant_identity",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "evidence_type IN "
            "('verified_source_termination', 'authorized_admin_resolution')",
            name="ck_dq_release_evidence_type",
        ),
        CheckConstraint(
            "evidence_status IN ('recorded', 'confirmed', 'rejected')",
            name="ck_dq_release_evidence_status",
        ),
        CheckConstraint(
            "(evidence_type = 'verified_source_termination' "
            "AND resolution_grant_id IS NULL) "
            "OR (evidence_type = 'authorized_admin_resolution' "
            "AND resolution_grant_id IS NOT NULL)",
            name="ck_dq_release_evidence_grant_type",
        ),
        CheckConstraint(
            "(evidence_status = 'recorded' "
            "AND verified_at IS NULL AND verified_by_user_id IS NULL) "
            "OR (evidence_status IN ('confirmed', 'rejected') "
            "AND verified_at IS NOT NULL "
            "AND verified_by_user_id IS NOT NULL)",
            name="ck_dq_release_evidence_review_state",
        ),
        CheckConstraint(
            "NULLIF(BTRIM(reason), '') IS NOT NULL "
            "AND NULLIF(BTRIM(evidence_reference), '') IS NOT NULL",
            name="ck_dq_release_evidence_required_details",
        ),
        Index(
            "ix_dq_release_evidence_ownership_status",
            "ownership_id",
            "evidence_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    ownership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    resolution_grant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    evidence_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    evidence_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="recorded",
        server_default="recorded",
    )

    reason: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    evidence_reference: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
