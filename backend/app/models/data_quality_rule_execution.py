"""Persist aggregate results for Data Quality rule executions."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    BigInteger,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DataQualityRuleExecution(Base):
    __tablename__ = "data_quality_rule_executions"

    __table_args__ = (
        ForeignKeyConstraint(
            ["rule_id", "version_id"],
            [
                "data_quality_rule_versions.rule_id",
                "data_quality_rule_versions.id",
            ],
            name="fk_dq_execution_rule_version_identity",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('succeeded', 'failed')",
            name="ck_dq_execution_status",
        ),
        CheckConstraint(
            "total_count IS NULL OR total_count >= 0",
            name="ck_dq_execution_total_nonnegative",
        ),
        CheckConstraint(
            "passing_count IS NULL OR passing_count >= 0",
            name="ck_dq_execution_passing_nonnegative",
        ),
        CheckConstraint(
            "violation_count IS NULL OR violation_count >= 0",
            name="ck_dq_execution_violations_nonnegative",
        ),
        CheckConstraint(
            """
            status != 'succeeded'
            OR (
                total_count IS NOT NULL
                AND passing_count IS NOT NULL
                AND violation_count IS NOT NULL
                AND total_count = passing_count + violation_count
            )
            """,
            name="ck_dq_execution_success_counts",
        ),
        Index("ix_dq_execution_project_id", "project_id"),
        Index("ix_dq_execution_actor_user_id", "actor_user_id"),
        Index("ix_dq_execution_rule_id", "rule_id"),
        Index("ix_dq_execution_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", name="fk_dq_execution_project", ondelete="RESTRICT"),
        nullable=False,
    )

    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_dq_execution_actor_user", ondelete="RESTRICT"),
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

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    total_count: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    passing_count: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    violation_count: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
