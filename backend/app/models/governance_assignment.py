import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class GovernanceAssignment(Base):
    __tablename__ = "governance_assignments"

    __table_args__ = (
        ForeignKeyConstraint(
            ["client_id", "person_id"],
            ["governance_people.client_id", "governance_people.id"],
            name="fk_governance_assignment_person_client",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["client_id", "department_id"],
            ["governance_departments.client_id", "governance_departments.id"],
            name="fk_governance_assignment_department_client",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "role IN ("
            "'executive_accountable_owner', "
            "'department_data_owner', "
            "'data_steward'"
            ")",
            name="ck_governance_assignment_role",
        ),
        CheckConstraint(
            "effective_end IS NULL OR "
            "effective_start IS NULL OR "
            "effective_end >= effective_start",
            name="ck_governance_assignment_dates",
        ),
        Index(
            "ix_governance_assignments_client_department_role",
            "client_id",
            "department_id",
            "role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    effective_start: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    effective_end: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
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

    person = relationship("GovernancePerson", viewonly=True)
    department = relationship("GovernanceDepartment", viewonly=True)
