import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, false, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class PostgreSQLConnectionIdentity(Base):
    """Non-secret registered destination for a PostgreSQL data source."""

    __tablename__ = "postgresql_connection_identities"
    __table_args__ = (
        CheckConstraint(
            "port BETWEEN 1 AND 65535",
            name="ck_postgresql_connection_identity_port",
        ),
        CheckConstraint(
            "connection_revision >= 1",
            name="ck_postgresql_connection_identity_revision_positive",
        ),
        CheckConstraint(
            "NOT is_verified OR verified_at IS NOT NULL",
            name="ck_postgresql_connection_identity_verified_at",
        ),
    )

    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        primary_key=True,
    )

    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    database_name: Mapped[str] = mapped_column(String(255), nullable=False)

    connection_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    data_source = relationship("DataSource")
