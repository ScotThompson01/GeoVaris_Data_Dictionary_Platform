"""Audit events for Data Quality rule version lifecycle changes."""

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


class DataQualityRuleAuditEvent(Base):
    __tablename__ = "data_quality_rule_audit_events"

    __table_args__ = (
        ForeignKeyConstraint(
            ["rule_id", "version_id"],
            [
                "data_quality_rule_versions.rule_id",
                "data_quality_rule_versions.id",
            ],
            name="fk_dq_rule_audit_version_identity",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "event_type IN ('version.approved', 'version.activated')",
            name="ck_dq_rule_audit_event_type",
        ),
        Index("ix_dq_rule_audit_project_id", "project_id"),
        Index("ix_dq_rule_audit_actor_user_id", "actor_user_id"),
        Index("ix_dq_rule_audit_rule_id", "rule_id"),
        Index("ix_dq_rule_audit_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )

    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    old_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    new_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
