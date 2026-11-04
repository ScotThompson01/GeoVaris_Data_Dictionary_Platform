"""Schema regression tests for reservation-to-workload source identity."""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint
from sqlalchemy.dialects import postgresql

from app.models.data_quality_execution_capacity_reservation import (
    DataQualityExecutionCapacityReservation as Reservation,
)


def test_ownership_source_identity_is_required():
    table = Reservation.__table__
    assert table.c.ownership_data_source_id.nullable is False


def test_workload_composite_fk_has_no_nullable_columns():
    table = Reservation.__table__
    matches = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and constraint.name == "fk_dq_reservation_ownership_source"
    ]
    assert len(matches) == 1

    constraint = matches[0]
    assert list(constraint.columns.keys()) == [
        "ownership_id",
        "ownership_data_source_id",
    ]
    assert all(not column.nullable for column in constraint.columns)
    assert [element.target_fullname for element in constraint.elements] == [
        "data_quality_workload_ownership.id",
        "data_quality_workload_ownership.data_source_id",
    ]
    assert constraint.ondelete == "RESTRICT"


def test_installation_reservation_keeps_nullable_scope_source():
    table = Reservation.__table__
    assert table.c.data_source_id.nullable is True
    assert table.c.ownership_data_source_id.nullable is False


def test_source_reservation_must_match_workload_source():
    table = Reservation.__table__
    matches = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_dq_reservation_source_scope"
    ]
    assert len(matches) == 1

    expression = str(
        matches[0].sqltext.compile(dialect=postgresql.dialect())
    )

    assert "reservation_scope = 'installation'" in expression
    assert "data_source_id IS NULL" in expression
    assert "reservation_scope = 'source'" in expression
    assert "data_source_id = ownership_data_source_id" in expression


def test_capacity_control_scope_relationship_is_preserved():
    table = Reservation.__table__
    names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert "fk_dq_reservation_capacity_scope" in names
    assert "fk_dq_reservation_capacity_source" in names
