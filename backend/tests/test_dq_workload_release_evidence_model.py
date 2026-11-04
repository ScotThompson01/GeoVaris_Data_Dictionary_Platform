"""Structural checks for proposed durable workload release evidence."""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql

from app.models.data_quality_workload_ownership import DataQualityWorkloadOwnership
from app.models.data_quality_workload_resolution_grant import (
    DataQualityWorkloadResolutionGrant,
)
from app.models.data_quality_workload_release_evidence import (
    DataQualityWorkloadReleaseEvidence,
)


def named_constraint(table, name, kind):
    matches = [
        constraint for constraint in table.constraints
        if isinstance(constraint, kind) and constraint.name == name
    ]
    assert len(matches) == 1
    return matches[0]


def test_workload_composite_identity():
    constraint = named_constraint(
        DataQualityWorkloadOwnership.__table__,
        "uq_dq_workload_id_project_source",
        UniqueConstraint,
    )
    assert list(constraint.columns.keys()) == [
        "id", "project_id", "data_source_id"
    ]


def test_grant_composite_identity():
    constraint = named_constraint(
        DataQualityWorkloadResolutionGrant.__table__,
        "uq_dq_resolution_grant_id_project_user",
        UniqueConstraint,
    )
    assert list(constraint.columns.keys()) == [
        "id", "project_id", "user_id"
    ]


def test_evidence_workload_composite_foreign_key():
    constraint = named_constraint(
        DataQualityWorkloadReleaseEvidence.__table__,
        "fk_dq_release_evidence_workload_identity",
        ForeignKeyConstraint,
    )
    assert [e.target_fullname for e in constraint.elements] == [
        "data_quality_workload_ownership.id",
        "data_quality_workload_ownership.project_id",
        "data_quality_workload_ownership.data_source_id",
    ]
    assert constraint.ondelete == "RESTRICT"


def test_evidence_grant_composite_foreign_key():
    constraint = named_constraint(
        DataQualityWorkloadReleaseEvidence.__table__,
        "fk_dq_release_evidence_resolution_grant_identity",
        ForeignKeyConstraint,
    )
    assert [e.target_fullname for e in constraint.elements] == [
        "data_quality_workload_resolution_grants.id",
        "data_quality_workload_resolution_grants.project_id",
        "data_quality_workload_resolution_grants.user_id",
    ]
    assert constraint.ondelete == "RESTRICT"


def test_evidence_defaults_to_unconfirmed_recorded_state():
    column = DataQualityWorkloadReleaseEvidence.__table__.c.evidence_status
    assert column.nullable is False
    assert column.server_default.arg == "recorded"


def test_evidence_requires_review_identity_for_decisions():
    table = DataQualityWorkloadReleaseEvidence.__table__
    constraint = named_constraint(
        table, "ck_dq_release_evidence_review_state", CheckConstraint
    )
    expression = str(constraint.sqltext.compile(dialect=postgresql.dialect()))
    assert "verified_at IS NOT NULL" in expression
    assert "verified_by_user_id IS NOT NULL" in expression
    assert "evidence_status = 'recorded'" in expression


def test_evidence_requires_grant_for_admin_resolution_only():
    constraint = named_constraint(
        DataQualityWorkloadReleaseEvidence.__table__,
        "ck_dq_release_evidence_grant_type",
        CheckConstraint,
    )
    expression = str(constraint.sqltext.compile(dialect=postgresql.dialect()))
    assert "resolution_grant_id IS NULL" in expression
    assert "resolution_grant_id IS NOT NULL" in expression


def test_evidence_preserves_project_and_source_identity():
    table = DataQualityWorkloadReleaseEvidence.__table__
    assert table.c.project_id.nullable is False
    assert table.c.data_source_id.nullable is False
    assert table.c.actor_user_id.nullable is False


def test_evidence_has_required_reason_and_reference():
    table = DataQualityWorkloadReleaseEvidence.__table__
    constraint = named_constraint(
        table, "ck_dq_release_evidence_required_details", CheckConstraint
    )
    expression = str(constraint.sqltext.compile(dialect=postgresql.dialect()))
    assert "BTRIM(reason)" in expression
    assert "BTRIM(evidence_reference)" in expression
