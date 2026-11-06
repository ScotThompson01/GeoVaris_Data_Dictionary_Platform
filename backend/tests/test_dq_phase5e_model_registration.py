"""Validate Phase 5E model registration for Alembic metadata."""

from app.db import base
from app.db.session import Base


EXPECTED_TABLES = {
    "data_quality_rule_executions",
    "data_quality_execution_capacity_controls",
    "data_quality_workload_ownership",
    "data_quality_execution_capacity_reservations",
    "data_quality_workload_resolution_grants",
    "data_quality_workload_release_evidence",
}


def test_all_phase5e_tables_are_registered():
    assert EXPECTED_TABLES.issubset(Base.metadata.tables)


def test_phase5e_models_are_exported():
    assert {
        "DataQualityRuleExecution",
        "DataQualityExecutionCapacityControl",
        "DataQualityWorkloadOwnership",
        "DataQualityExecutionCapacityReservation",
        "DataQualityWorkloadResolutionGrant",
        "DataQualityWorkloadReleaseEvidence",
    }.issubset(set(base.__all__))


def test_reservation_identity_constraint_is_registered():
    table = Base.metadata.tables[
        "data_quality_execution_capacity_reservations"
    ]
    assert table.c.ownership_data_source_id.nullable is False

    constraints = {
        constraint.name for constraint in table.constraints
    }
    assert "fk_dq_reservation_ownership_source" in constraints


def test_release_evidence_table_is_registered():
    table = Base.metadata.tables[
        "data_quality_workload_release_evidence"
    ]
    assert table.c.project_id.nullable is False
    assert table.c.ownership_id.nullable is False
