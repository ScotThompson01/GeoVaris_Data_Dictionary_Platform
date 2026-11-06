"""Persistent capacity reservations for Phase 5E execution admission.

Schema proposal only. No workload execution is authorized.
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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DataQualityExecutionCapacityReservation(Base):
    __tablename__ = "data_quality_execution_capacity_reservations"

    __table_args__ = (
        ForeignKeyConstraint(
            ["ownership_id", "ownership_data_source_id"],
            [
                "data_quality_workload_ownership.id",
                "data_quality_workload_ownership.data_source_id",
            ],
            name="fk_dq_reservation_ownership_source",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["capacity_control_id", "reservation_scope", "data_source_id"],
            [
                "data_quality_execution_capacity_controls.id",
                "data_quality_execution_capacity_controls.scope_type",
                "data_quality_execution_capacity_controls.data_source_id",
            ],
            name="fk_dq_reservation_capacity_source",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(reservation_scope = 'installation' AND data_source_id IS NULL) "
            "OR (reservation_scope = 'source' "
            "AND data_source_id IS NOT NULL "
            "AND data_source_id = ownership_data_source_id)",
            name="ck_dq_reservation_source_scope",
        ),
        ForeignKeyConstraint(
            ["capacity_control_id", "reservation_scope"],
            [
                "data_quality_execution_capacity_controls.id",
                "data_quality_execution_capacity_controls.scope_type",
            ],
            name="fk_dq_reservation_capacity_scope",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "reservation_scope IN ('installation', 'source')",
            name="ck_dq_reservation_scope",
        ),
        CheckConstraint(
            "reservation_state IN ('reserved', 'unresolved', 'released')",
            name="ck_dq_reservation_state",
        ),
        CheckConstraint(
            "("
            "reservation_state = 'released' "
            "AND released_at IS NOT NULL "
            "AND NULLIF(BTRIM(release_actor), '') IS NOT NULL "
            "AND NULLIF(BTRIM(release_reason), '') IS NOT NULL "
            "AND NULLIF(BTRIM(release_evidence_reference), '') IS NOT NULL"
            ") OR ("
            "reservation_state IN ('reserved', 'unresolved') "
            "AND released_at IS NULL "
            "AND release_actor IS NULL "
            "AND release_reason IS NULL "
            "AND release_evidence_reference IS NULL"
            ")",
            name="ck_dq_reservation_release_audit",
        ),
        UniqueConstraint(
            "ownership_id",
            "reservation_scope",
            name="uq_dq_reservation_ownership_scope",
        ),
        ForeignKeyConstraint(
            ["ownership_id"],
            ["data_quality_workload_ownership.id"],
            name="fk_dq_reservation_ownership",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_dq_reservation_capacity_state",
            "capacity_control_id",
            "reservation_state",
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

    capacity_control_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    ownership_data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    data_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    reservation_scope: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    reservation_state: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="reserved",
        server_default="reserved",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
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

    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
