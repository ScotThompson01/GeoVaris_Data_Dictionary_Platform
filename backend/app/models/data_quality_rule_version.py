"""Versioned definitions for field-level Data Quality range rules."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DataQualityRuleVersion(Base):
    __tablename__ = "data_quality_rule_versions"

    __table_args__ = (
        UniqueConstraint(
            "rule_id",
            "id",
            name="uq_data_quality_rule_version_parent_identity",
        ),
        UniqueConstraint(
            "rule_id",
            "version_number",
            name="uq_data_quality_rule_version_number",
        ),
        CheckConstraint(
            "rule_type = 'range'",
            name="ck_data_quality_rule_version_type",
        ),
        CheckConstraint(
            "quality_dimension = 'validity'",
            name="ck_data_quality_rule_version_dimension",
        ),
        CheckConstraint(
            "version_number >= 1",
            name="ck_data_quality_rule_version_positive",
        ),
        CheckConstraint(
            "min_value <= max_value",
            name="ck_data_quality_rule_version_range",
        ),
        CheckConstraint(
            "status IN ('draft', 'approved', 'retired')",
            name="ck_data_quality_rule_version_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_quality_rules.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    rule_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="range",
        server_default="range",
    )

    quality_dimension: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="validity",
        server_default="validity",
    )

    min_value: Mapped[Decimal] = mapped_column(
        Numeric(precision=24, scale=10),
        nullable=False,
    )

    max_value: Mapped[Decimal] = mapped_column(
        Numeric(precision=24, scale=10),
        nullable=False,
    )

    null_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
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
