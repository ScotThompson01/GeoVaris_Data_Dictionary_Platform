"""Focused consistency checks; no release or database operations."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.data_quality_workload_release_evidence_integrity import (
    validate_release_evidence_record_consistency as validate,
)

NOW = datetime(2026, 11, 4, tzinfo=timezone.utc)


def scenario(admin=False):
    project_id, source_id, ownership_id, actor_id = (
        uuid4(), uuid4(), uuid4(), uuid4()
    )
    ownership = SimpleNamespace(
        id=ownership_id,
        project_id=project_id,
        data_source_id=source_id,
        ownership_state="unresolved",
    )
    grant = (
        SimpleNamespace(
            id=uuid4(),
            project_id=project_id,
            user_id=actor_id,
            granted_by_user_id=uuid4(),
            created_at=NOW - timedelta(days=1),
            revoked_at=None,
        )
        if admin else None
    )
    evidence = SimpleNamespace(
        id=uuid4(),
        ownership_id=ownership_id,
        project_id=project_id,
        data_source_id=source_id,
        actor_user_id=actor_id,
        resolution_grant_id=grant.id if grant else None,
        evidence_type=(
            "authorized_admin_resolution"
            if admin else "verified_source_termination"
        ),
        evidence_status="confirmed",
        reason="Documented protected workload resolution",
        evidence_reference="local-evidence-reference",
        verified_by_user_id=uuid4(),
        created_at=NOW,
        verified_at=NOW + timedelta(minutes=1),
    )
    return evidence, ownership, grant


@pytest.mark.parametrize("admin", [False, True])
def test_consistent_snapshots_pass_consistency_only(admin):
    evidence, ownership, grant = scenario(admin)
    assert validate(
        evidence=evidence, ownership=ownership, resolution_grant=grant
    ) is None


@pytest.mark.parametrize("field", [
    "ownership_id", "project_id", "data_source_id"
])
def test_cross_scope_identity_fails(field):
    evidence, ownership, grant = scenario()
    setattr(evidence, field, uuid4())
    with pytest.raises(ValueError, match="identity mismatch"):
        validate(evidence=evidence, ownership=ownership)


@pytest.mark.parametrize("state", ["recorded", "rejected", "unknown"])
def test_unconfirmed_evidence_fails(state):
    evidence, ownership, grant = scenario()
    evidence.evidence_status = state
    with pytest.raises(ValueError, match="not been confirmed"):
        validate(evidence=evidence, ownership=ownership)


def test_released_workload_fails():
    evidence, ownership, grant = scenario()
    ownership.ownership_state = "released"
    with pytest.raises(ValueError, match="not protected"):
        validate(evidence=evidence, ownership=ownership)


def test_missing_review_identity_fails():
    evidence, ownership, grant = scenario()
    evidence.verified_by_user_id = None
    with pytest.raises(ValueError, match="reviewer"):
        validate(evidence=evidence, ownership=ownership)


def test_review_before_creation_fails():
    evidence, ownership, grant = scenario()
    evidence.verified_at = NOW - timedelta(minutes=1)
    with pytest.raises(ValueError, match="precedes"):
        validate(evidence=evidence, ownership=ownership)


def test_missing_admin_grant_fails():
    evidence, ownership, grant = scenario(admin=True)
    with pytest.raises(ValueError, match="grant is required"):
        validate(evidence=evidence, ownership=ownership)


def test_revoked_admin_grant_fails():
    evidence, ownership, grant = scenario(admin=True)
    grant.revoked_at = NOW
    with pytest.raises(ValueError, match="revoked"):
        validate(
            evidence=evidence, ownership=ownership,
            resolution_grant=grant
        )


def test_cross_project_admin_grant_fails():
    evidence, ownership, grant = scenario(admin=True)
    grant.project_id = uuid4()
    with pytest.raises(ValueError, match="grant identity mismatch"):
        validate(
            evidence=evidence, ownership=ownership,
            resolution_grant=grant
        )


def test_admin_grant_for_other_user_fails():
    evidence, ownership, grant = scenario(admin=True)
    grant.user_id = uuid4()
    with pytest.raises(ValueError, match="grant identity mismatch"):
        validate(
            evidence=evidence, ownership=ownership,
            resolution_grant=grant
        )


def test_grant_created_after_evidence_fails():
    evidence, ownership, grant = scenario(admin=True)
    grant.created_at = NOW + timedelta(minutes=1)
    with pytest.raises(ValueError, match="postdates"):
        validate(
            evidence=evidence, ownership=ownership,
            resolution_grant=grant
        )


def test_termination_evidence_with_admin_grant_fails():
    evidence, ownership, grant = scenario()
    extra_grant = SimpleNamespace(id=uuid4())
    with pytest.raises(ValueError, match="cannot use"):
        validate(
            evidence=evidence, ownership=ownership,
            resolution_grant=extra_grant
        )


def test_unknown_evidence_type_fails():
    evidence, ownership, grant = scenario()
    evidence.evidence_type = "untrusted"
    with pytest.raises(ValueError, match="Unknown"):
        validate(evidence=evidence, ownership=ownership)


def test_blank_reference_fails():
    evidence, ownership, grant = scenario()
    evidence.evidence_reference = "   "
    with pytest.raises(ValueError, match="reference"):
        validate(evidence=evidence, ownership=ownership)


def test_missing_evidence_fails():
    _, ownership, _ = scenario()
    with pytest.raises(ValueError, match="required"):
        validate(evidence=None, ownership=ownership)
