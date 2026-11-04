"""Fail-closed tests for internal persisted release validation."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services import data_quality_persisted_release_validation as service


def scenario():
    owner = SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        data_source_id=uuid4(),
        ownership_state="unresolved",
    )
    actor_id = uuid4()
    evidence = SimpleNamespace(
        evidence_type="authorized_admin_resolution",
        actor_user_id=actor_id,
    )
    return owner, actor_id, evidence


def test_valid_evidence_is_returned_after_scoped_lookup(monkeypatch):
    owner, actor_id, evidence = scenario()
    evidence_id = uuid4()
    db = object()
    calls = []

    def lookup(session, **kwargs):
        calls.append((session, kwargs))
        return evidence

    monkeypatch.setattr(service, "load_consistent_release_evidence", lookup)

    assert service.validate_persisted_admin_resolution_under_locks(
        db,
        owner,
        evidence_id=evidence_id,
        trusted_actor_user_id=actor_id,
    ) is evidence

    assert calls == [
        (
            db,
            {
                "evidence_id": evidence_id,
                "ownership_id": owner.id,
                "project_id": owner.project_id,
                "data_source_id": owner.data_source_id,
            },
        )
    ]


@pytest.mark.parametrize(
    "evidence_type",
    ["verified_source_termination", "unknown", None],
)
def test_non_admin_evidence_is_rejected(monkeypatch, evidence_type):
    owner, actor_id, evidence = scenario()
    evidence.evidence_type = evidence_type
    monkeypatch.setattr(
        service,
        "load_consistent_release_evidence",
        lambda *args, **kwargs: evidence,
    )

    with pytest.raises(ValueError, match="Administrator resolution"):
        service.validate_persisted_admin_resolution_under_locks(
            object(),
            owner,
            evidence_id=uuid4(),
            trusted_actor_user_id=actor_id,
        )


def test_mismatched_actor_is_rejected(monkeypatch):
    owner, actor_id, evidence = scenario()
    monkeypatch.setattr(
        service,
        "load_consistent_release_evidence",
        lambda *args, **kwargs: evidence,
    )

    with pytest.raises(ValueError, match="Trusted actor"):
        service.validate_persisted_admin_resolution_under_locks(
            object(),
            owner,
            evidence_id=uuid4(),
            trusted_actor_user_id=uuid4(),
        )


@pytest.mark.parametrize("state", ["released", "unknown", None])
def test_unprotected_workload_is_rejected_before_lookup(
    monkeypatch, state
):
    owner, actor_id, evidence = scenario()
    owner.ownership_state = state

    def forbidden_lookup(*args, **kwargs):
        pytest.fail("Lookup must not run for an unprotected workload.")

    monkeypatch.setattr(
        service,
        "load_consistent_release_evidence",
        forbidden_lookup,
    )

    with pytest.raises(ValueError, match="not protected"):
        service.validate_persisted_admin_resolution_under_locks(
            object(),
            owner,
            evidence_id=uuid4(),
            trusted_actor_user_id=actor_id,
        )


def test_missing_evidence_fails_closed(monkeypatch):
    owner, actor_id, evidence = scenario()

    def reject(*args, **kwargs):
        raise ValueError("Active administrator resolution grant not found.")

    monkeypatch.setattr(
        service,
        "load_consistent_release_evidence",
        reject,
    )

    with pytest.raises(ValueError, match="Active administrator"):
        service.validate_persisted_admin_resolution_under_locks(
            object(),
            owner,
            evidence_id=uuid4(),
            trusted_actor_user_id=actor_id,
        )


def test_invalid_identity_is_rejected_before_lookup(monkeypatch):
    owner, actor_id, evidence = scenario()

    def forbidden_lookup(*args, **kwargs):
        pytest.fail("Lookup must not run for invalid identities.")

    monkeypatch.setattr(
        service,
        "load_consistent_release_evidence",
        forbidden_lookup,
    )

    with pytest.raises(ValueError, match="Invalid persisted"):
        service.validate_persisted_admin_resolution_under_locks(
            object(),
            owner,
            evidence_id="not-a-uuid",
            trusted_actor_user_id=actor_id,
        )
