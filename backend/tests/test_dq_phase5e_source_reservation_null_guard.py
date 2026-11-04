"""Prevent NULL source identities from bypassing reservation checks."""

from pathlib import Path

from sqlalchemy import CheckConstraint
from sqlalchemy.dialects import postgresql

from app.models.data_quality_execution_capacity_reservation import (
    DataQualityExecutionCapacityReservation,
)


EXPECTED = (
    "reservation_scope = 'source' "
    "AND data_source_id IS NOT NULL "
    "AND data_source_id = ownership_data_source_id"
)


def test_source_reservation_requires_nonnull_source():
    table = DataQualityExecutionCapacityReservation.__table__

    constraints = [
        item
        for item in table.constraints
        if isinstance(item, CheckConstraint)
        and item.name == "ck_dq_reservation_source_scope"
    ]

    assert len(constraints) == 1

    sql = str(
        constraints[0].sqltext.compile(
            dialect=postgresql.dialect()
        )
    )

    assert EXPECTED in sql


def test_unapplied_migration_contains_same_null_guard():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0025_create_phase5e_execution_protection.py"
    )

    content = path.read_text(encoding="utf-8")

    assert EXPECTED in content
    assert content.count(EXPECTED) == 1


def test_installation_reservations_still_allow_null_scope_source():
    table = DataQualityExecutionCapacityReservation.__table__

    assert table.c.data_source_id.nullable is True
    assert table.c.ownership_data_source_id.nullable is False
