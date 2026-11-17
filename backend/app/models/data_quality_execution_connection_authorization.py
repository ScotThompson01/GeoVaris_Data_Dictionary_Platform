"""Non-secret authorization evidence bound to a protected DQ execution.

Schema only. This model does not authorize connections or source work.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DataQualityExecutionConnectionAuthorization(Base):
    __tablename__ = "data_quality_execution_connection_authorizations"

    __table_args__ = (
        ForeignKeyConstraint(
            ["execution_id", "project_id", "data_source_id"],
            [
                "data_quality_workload_ownership.execution_id",
                "data_quality_workload_ownership.project_id",
                "data_quality_workload_ownership.data_source_id",
            ],
            name="fk_dq_connection_auth_execution_source",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["data_source_id"],
            ["postgresql_connection_identities.data_source_id"],
            name="fk_dq_connection_auth_registered_source",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "connection_revision >= 1",
            name="ck_dq_connection_auth_positive_revision",
        ),
        CheckConstraint(
            "authorized_port BETWEEN 1 AND 65535",
            name="ck_dq_connection_auth_valid_port",
        ),
    )

    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    connection_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    authorized_host: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    authorized_port: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    authorized_database: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    authorized_ip: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
    )

    authorized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
