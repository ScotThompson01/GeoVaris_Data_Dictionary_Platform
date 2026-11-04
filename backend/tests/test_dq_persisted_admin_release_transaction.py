"""Fail-closed tests for internal persisted administrator release."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services import (
    data_quality_persisted_admin_release_transaction as service,
)
from test_dq_execution_release_transaction import scenario


def setup_case(monkeypatch):
    db, owner, reservations, kwargs = scenario("unresolved")
    actor_id = uuid4()
    evidence_id = uuid4()

    evidence = SimpleNamespace(
        reason="Verified administrator resolution",
        evidence_reference="admin-evidence-001",
        actor_user_id=actor_id,
        evidence_type="authorized_admin_resolution",
    )

    calls = []

    def validator(session, locked_owner, **validation_kwargs):
        calls.append(
            (
                session,
                locked_owner,
                len(session.reads),
                tuple(
                    reservation.reservation_state
                    for reservation in reservations
                ),
                validation_kwargs,
            )
        )
        return evidence

    monkeypatch.setattr(
        service,
        "validate_persisted_admin_resolution_under_locks",
        validator,
    )

    release_kwargs = dict(
        project_id=owner.project_id,
        ownership_id=owner.id,
        data_source_id=owner.data_source_id,
        evidence_id=evidence_id,
        trusted_actor_user_id=actor_id,
        reason=evidence.reason,
        evidence_reference=evidence.evidence_reference,
    )

    return db, owner, reservations, evidence, calls, release_kwargs


def test_valid_evidence_stages_release_under_locks(monkeypatch):
    db, owner, reservations, evidence, calls, kwargs = setup_case(
        monkeypatch
    )

    service.stage_persisted_admin_resolution(db, **kwargs)

    assert len(calls) == 1
    assert calls[0][0] is db
    assert calls[0][1] is owner
    assert calls[0][2] == 4
    assert calls[0][3] == ("unresolved", "unresolved")
    assert calls[0][4] == {
        "evidence_id": kwargs["evidence_id"],
        "trusted_actor_user_id": kwargs["trusted_actor_user_id"],
    }

    assert db.flush_count == 1
    assert owner.ownership_state == "released"
    assert all(
        reservation.reservation_state == "released"
        for reservation in reservations
    )


@pytest.mark.parametrize(
    "message",
    [
        "Active administrator resolution grant not found.",
        "Resolution actor lacks project membership.",
        "Evidence has not been confirmed.",
        "Trusted actor does not match release evidence.",
    ],
)
def test_rejected_evidence_preserves_capacity(monkeypatch, message):
    db, owner, reservations, evidence, calls, kwargs = setup_case(
        monkeypatch
    )

    def reject(*args, **validation_kwargs):
        raise ValueError(message)

    monkeypatch.setattr(
        service,
        "validate_persisted_admin_resolution_under_locks",
        reject,
    )

    with pytest.raises(ValueError) as exc_info:
        service.stage_persisted_admin_resolution(db, **kwargs)

    assert str(exc_info.value) == message
    assert len(db.reads) == 4
    assert db.flush_count == 0
    assert owner.ownership_state == "unresolved"
    assert all(
        reservation.reservation_state == "unresolved"
        for reservation in reservations
    )


@pytest.mark.parametrize(
    "field",
    ["reason", "evidence_reference"],
)
def test_mismatched_audit_details_preserve_capacity(
    monkeypatch, field
):
    db, owner, reservations, evidence, calls, kwargs = setup_case(
        monkeypatch
    )
    kwargs[field] = "Unrelated audit detail"

    with pytest.raises(ValueError, match="audit details"):
        service.stage_persisted_admin_resolution(db, **kwargs)

    assert len(calls) == 1
    assert db.flush_count == 0
    assert owner.ownership_state == "unresolved"
    assert all(
        reservation.reservation_state == "unresolved"
        for reservation in reservations
    )


def test_invalid_actor_rejected_before_database_access(monkeypatch):
    db, owner, reservations, evidence, calls, kwargs = setup_case(
        monkeypatch
    )
    kwargs["trusted_actor_user_id"] = "not-a-uuid"

    with pytest.raises(ValueError, match="Invalid trusted_actor"):
        service.stage_persisted_admin_resolution(db, **kwargs)

    assert db.reads == []
    assert db.flush_count == 0
    assert owner.ownership_state == "unresolved"


def test_missing_capacity_control_prevents_evidence_validation(
    monkeypatch,
):
    db, owner, reservations, evidence, calls, kwargs = setup_case(
        monkeypatch
    )
    db.locked_records[0] = None

    with pytest.raises(ValueError, match="Installation capacity"):
        service.stage_persisted_admin_resolution(db, **kwargs)

    assert calls == []
    assert db.flush_count == 0
    assert owner.ownership_state == "unresolved"
    assert all(
        reservation.reservation_state == "unresolved"
        for reservation in reservations
    )
