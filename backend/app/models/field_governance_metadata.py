import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class FieldGovernanceMetadata(Base):
    __tablename__ = "field_governance_metadata"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    data_field_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "data_fields.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    business_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    business_definition: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    department: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    data_owner: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    data_steward: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    business_process: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    system_of_record: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_cde: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    classification: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    approval_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="draft",
        server_default="draft",
    )

    notes: Mapped[str | None] = mapped_column(
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

    data_field = relationship(
        "DataField",
        back_populates="governance_metadata",
    )
    