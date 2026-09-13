import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class DataField(Base):
    __tablename__ = "data_fields"
    __table_args__ = (
        UniqueConstraint(
            "source_object_id",
            "field_name",
            name="uq_data_fields_object_name",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    source_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    field_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    ordinal_position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    native_data_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    normalized_data_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    max_length: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    numeric_precision: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    numeric_scale: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    is_nullable: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    is_primary_key: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    is_unique: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    default_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source_comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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

    source_object = relationship(
        "SourceObject",
        back_populates="data_fields",
    )

    profiling_results = relationship(
        "ProfilingResult",
        back_populates="data_field",
        cascade="all, delete-orphan",
    )