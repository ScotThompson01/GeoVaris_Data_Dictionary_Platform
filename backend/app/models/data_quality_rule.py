"""Durable identity for a field-level Data Quality rule."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DataQualityRule(Base):
    __tablename__ = "data_quality_rules"
    __table_args__ = (
        ForeignKeyConstraint(
            ["id", "active_version_id"],
            ["data_quality_rule_versions.rule_id", "data_quality_rule_versions.id"],
            name="fk_data_quality_rule_active_version",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'retired')",
            name="ck_data_quality_rule_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    data_field_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_fields.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    active_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    rule_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="draft",
        server_default="draft",
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
