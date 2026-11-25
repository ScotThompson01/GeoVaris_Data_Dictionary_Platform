"""Non-secret PostgreSQL profiling account approval metadata."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PostgreSQLProfilingAccountApprovalRecord(Base):
    """Persist an explicit, revision-bound database account approval.

    This record contains no database password or authentication token.
    Revoked records are retained as approval history.

    Creating a record is a privileged governance operation. This model
    does not independently authorize record creation or modification.
    """

    __tablename__ = "postgresql_profiling_account_approvals"

    __table_args__ = (
        CheckConstraint(
            "connection_revision > 0",
            name="ck_pg_profile_account_revision",
        ),
        CheckConstraint(
            "length(trim(username)) > 0",
            name="ck_pg_profile_account_username",
        ),
        CheckConstraint(
            """
            (
                revoked_at IS NULL
                AND revoked_by_user_id IS NULL
            )
            OR
            (
                revoked_at IS NOT NULL
                AND revoked_by_user_id IS NOT NULL
                AND revoked_at >= approved_at
            )
            """,
            name="ck_pg_profile_account_revocation",
        ),
        Index(
            "uq_pg_profile_account_active",
            "data_source_id",
            "connection_revision",
            "username",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
            sqlite_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "postgresql_connection_identities.data_source_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    connection_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    username: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    approved_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
