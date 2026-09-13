import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ProfilingResult(Base):
    __tablename__ = "profiling_results"
    __table_args__ = (
        UniqueConstraint(
            "scan_id",
            "data_field_id",
            name="uq_profiling_results_scan_field",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    data_field_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_fields.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    row_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    null_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    null_percentage: Mapped[Decimal] = mapped_column(
        Numeric(7, 4),
        nullable=False,
    )

    distinct_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    distinct_percentage: Mapped[Decimal] = mapped_column(
        Numeric(7, 4),
        nullable=False,
    )

    minimum_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    maximum_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    minimum_length: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    maximum_length: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    scan = relationship(
        "Scan",
        back_populates="profiling_results",
    )

    data_field = relationship(
        "DataField",
        back_populates="profiling_results",
    )