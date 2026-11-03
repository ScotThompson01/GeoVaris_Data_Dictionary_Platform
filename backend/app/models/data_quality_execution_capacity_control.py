"""Persistent capacity-control rows for Phase 5E admission.

Model definition only. Does not authorize execution admission.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DataQualityExecutionCapacityControl(Base):
    __tablename__ = "data_quality_execution_capacity_controls"

    __table_args__ = (
        UniqueConstraint(
            "id",
            "scope_type",
            "data_source_id",
            name="uq_dq_capacity_control_id_scope_source",
        ),
        UniqueConstraint(
            "id",
            "scope_type",
            name="uq_dq_capacity_control_id_scope",
        ),
        Index(
            "uq_dq_capacity_single_installation",
            "scope_type",
            unique=True,
            postgresql_where=text("scope_type = 'installation'"),
        ),
        CheckConstraint(
            "scope_type IN ('installation', 'source')",
            name="ck_dq_capacity_control_scope",
        ),
        CheckConstraint(
            "max_concurrent >= 1",
            name="ck_dq_capacity_control_positive_limit",
        ),
        CheckConstraint(
            "(scope_type = 'installation' AND data_source_id IS NULL) "
            "OR (scope_type = 'source' AND data_source_id IS NOT NULL)",
            name="ck_dq_capacity_control_source_scope",
        ),
        UniqueConstraint(
            "data_source_id",
            name="uq_dq_capacity_control_data_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    scope_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    data_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="RESTRICT"),
        nullable=True,
    )

    max_concurrent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
