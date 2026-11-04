"""Isolated tests for internal transactional release staging."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.data_quality_execution_release_policy import (
    ReleaseEvidenceType,
)
from app.services.data_quality_execution_release_transaction import (
    stage_verified_workload_release,
)


class FakeResult:
    def __init__(self, records):
        self.records = records

    def all(self):
        return self.records


class FakeSession:
    def __init__(self, installation, source, ownership, reservations):
        self.locked_records = [installation, source, ownership]
        self.reservations = reservations
        self.reads = []
        self.flush_count = 0

    def scalar(self, statement):
        assert statement._for_update_arg is not None
        self.reads.append("control_or_ownership")
        return self.locked_records.pop(0)

    def scalars(self, statement):
        assert statement._for_update_arg is not None
        self.reads.append("reservations")
        return FakeResult(self.reservations)

    def flush(self):
        self.flush_count += 1


def scenario(state="reserved"):
    project_id, owner_id, source_id = uuid4(), uuid4(), uuid4()
    installation_id, source_control_id = uuid4(), uuid4()

    def audit_fields():
        return dict(
            released_at=None,
            release_actor=None,
            release_reason=None,
            release_evidence_reference=None,
        )

    ownership = SimpleNamespace(
        id=owner_id,
        project_id=project_id,
        data_source_id=source_id,
        ownership_state=state,
        **audit_fields(),
    )
    installation_control = SimpleNamespace(
        id=installation_id,
        scope_type="installation",
        data_source_id=None,
    )
    source_control = SimpleNamespace(
        id=source_control_id,
        scope_type="source",
        data_source_id=source_id,
    )

    reservations = [
        SimpleNamespace(
            id=uuid4(),
            ownership_id=owner_id,
            capacity_control_id=installation_id,
            ownership_data_source_id=source_id,
            data_source_id=None,
            reservation_scope="installation",
            reservation_state=state,
            **audit_fields(),
        ),
        SimpleNamespace(
            id=uuid4(),
            ownership_id=owner_id,
            capacity_control_id=source_control_id,
            ownership_data_source_id=source_id,
            data_source_id=source_id,
            reservation_scope="source",
            reservation_state=state,
            **audit_fields(),
        ),
    ]

    db = FakeSession(
        installation_control,
        source_control,
        ownership,
        reservations,
    )

    kwargs = dict(
        project_id=project_id,
        ownership_id=owner_id,
        data_source_id=source_id,
        evidence_type=ReleaseEvidenceType.VERIFIED_SOURCE_TERMINATION,
        actor="internal-verifier",
        reason="Verified source termination",
        evidence_reference="verification-record-001",
        source_termination_verified=True,
    )

    return db, ownership, reservations, kwargs


@pytest.mark.parametrize("state", ["reserved", "unresolved"])
def test_verified_release_stages_all_three_records(state):
    db, owner, reservations, kwargs = scenario(state)

    stage_verified_workload_release(db, **kwargs)

    assert db.flush_count == 1
    assert len(db.reads) == 4
    for record, field in (
        (owner, "ownership_state"),
        (reservations[0], "reservation_state"),
        (reservations[1], "reservation_state"),
    ):
        assert getattr(record, field) == "released"
        assert record.released_at is not None
        assert record.release_actor == "internal-verifier"
        assert record.release_evidence_reference == "verification-record-001"

    assert owner.released_at == reservations[0].released_at
    assert owner.released_at == reservations[1].released_at


@pytest.mark.parametrize("state", ["reserved", "unresolved"])
def test_unverified_termination_preserves_capacity(state):
    db, owner, reservations, kwargs = scenario(state)
    kwargs["source_termination_verified"] = False

    with pytest.raises(ValueError):
        stage_verified_workload_release(db, **kwargs)

    assert db.reads == []
    assert db.flush_count == 0
    assert owner.ownership_state == state
    assert all(r.reservation_state == state for r in reservations)


def test_authorized_resolution_can_stage_release():
    db, owner, reservations, kwargs = scenario("unresolved")
    kwargs.update(
        evidence_type=ReleaseEvidenceType.AUTHORIZED_ADMIN_RESOLUTION,
        source_termination_verified=False,
        administrator_authorized=True,
    )

    stage_verified_workload_release(db, **kwargs)

    assert owner.ownership_state == "released"
    assert all(r.reservation_state == "released" for r in reservations)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_reservation",
        "wrong_source",
        "wrong_installation_ownership_source",
        "wrong_source_ownership_source",
        "wrong_capacity_control",
        "mismatched_state",
        "already_released",
    ],
)
def test_integrity_failures_preserve_capacity(mutation):
    db, owner, reservations, kwargs = scenario("unresolved")

    if mutation == "missing_reservation":
        reservations.pop()
    elif mutation == "wrong_source":
        reservations[1].data_source_id = uuid4()
    elif mutation == "wrong_installation_ownership_source":
        reservations[0].ownership_data_source_id = uuid4()
    elif mutation == "wrong_source_ownership_source":
        reservations[1].ownership_data_source_id = uuid4()
    elif mutation == "wrong_capacity_control":
        reservations[1].capacity_control_id = uuid4()
    elif mutation == "mismatched_state":
        reservations[1].reservation_state = "reserved"
    elif mutation == "already_released":
        owner.ownership_state = "released"

    with pytest.raises(ValueError):
        stage_verified_workload_release(db, **kwargs)

    assert db.flush_count == 0
    assert owner.ownership_state != "released" or mutation == "already_released"
    assert all(r.reservation_state != "released" for r in reservations)


def test_missing_capacity_control_preserves_unresolved_workload():
    db, owner, reservations, kwargs = scenario("unresolved")
    db.locked_records[0] = None

    with pytest.raises(ValueError):
        stage_verified_workload_release(db, **kwargs)

    assert db.flush_count == 0
    assert owner.ownership_state == "unresolved"
    assert all(r.reservation_state == "unresolved" for r in reservations)


def test_invalid_identity_rejected_before_database_access():
    db, owner, reservations, kwargs = scenario("unresolved")
    kwargs["project_id"] = "not-a-uuid"

    with pytest.raises(ValueError):
        stage_verified_workload_release(db, **kwargs)

    assert db.reads == []
    assert db.flush_count == 0
    assert owner.ownership_state == "unresolved"
    assert all(r.reservation_state == "unresolved" for r in reservations)

from sqlalchemy.dialects import postgresql


def test_release_queries_use_expected_filters_and_lock_order():
    db, owner, reservations, kwargs = scenario("unresolved")
    captured = []

    original_scalar = db.scalar
    original_scalars = db.scalars

    def capture_scalar(statement):
        captured.append(statement)
        return original_scalar(statement)

    def capture_scalars(statement):
        captured.append(statement)
        return original_scalars(statement)

    db.scalar = capture_scalar
    db.scalars = capture_scalars

    stage_verified_workload_release(db, **kwargs)

    assert len(captured) == 4

    compiled = [
        statement.compile(dialect=postgresql.dialect())
        for statement in captured
    ]

    for statement in captured:
        assert statement._for_update_arg is not None

    sql = [str(item) for item in compiled]

    assert "data_quality_execution_capacity_controls" in sql[0]
    assert "scope_type" in sql[0]
    assert "data_quality_execution_capacity_controls" in sql[1]
    assert "data_source_id" in sql[1]

    assert "data_quality_workload_ownership" in sql[2]
    assert "project_id" in sql[2]
    assert "data_source_id" in sql[2]
    assert "data_quality_execution_capacity_reservations" in sql[3]
    assert "ownership_id" in sql[3]

    assert kwargs["data_source_id"] in compiled[1].params.values()
    assert kwargs["project_id"] in compiled[2].params.values()
    assert kwargs["ownership_id"] in compiled[2].params.values()
    assert kwargs["ownership_id"] in compiled[3].params.values()


@pytest.mark.parametrize(
    "change",
    [
        {"administrator_authorized": False},
        {"administrator_authorized": None},
    ],
)
def test_unapproved_administrator_resolution_keeps_capacity(change):
    db, owner, reservations, kwargs = scenario("unresolved")
    kwargs.update(
        evidence_type=ReleaseEvidenceType.AUTHORIZED_ADMIN_RESOLUTION,
        source_termination_verified=False,
        **change,
    )

    with pytest.raises(ValueError):
        stage_verified_workload_release(db, **kwargs)

    assert db.reads == []
    assert db.flush_count == 0
    assert owner.ownership_state == "unresolved"
    assert all(r.reservation_state == "unresolved" for r in reservations)


@pytest.mark.parametrize("field", ["actor", "reason", "evidence_reference"])
def test_missing_release_audit_data_keeps_capacity(field):
    db, owner, reservations, kwargs = scenario("unresolved")
    kwargs[field] = " "

    with pytest.raises(ValueError):
        stage_verified_workload_release(db, **kwargs)

    assert db.reads == []
    assert db.flush_count == 0
    assert owner.ownership_state == "unresolved"
    assert all(r.reservation_state == "unresolved" for r in reservations)


def test_extra_capacity_reservation_prevents_release():
    db, owner, reservations, kwargs = scenario("unresolved")
    from copy import copy

    reservations.append(copy(reservations[0]))

    with pytest.raises(ValueError):
        stage_verified_workload_release(db, **kwargs)

    assert db.flush_count == 0
    assert owner.ownership_state == "unresolved"
    assert all(r.reservation_state == "unresolved" for r in reservations)



def test_locked_validator_failure_preserves_capacity():
    db, owner, reservations, kwargs = scenario("unresolved")
    calls = []

    def reject_after_locks(session, locked_ownership):
        calls.append((session, locked_ownership, len(session.reads)))
        raise ValueError("Persisted authorization rejected.")

    kwargs["validate_under_locks"] = reject_after_locks

    with pytest.raises(ValueError, match="authorization rejected"):
        stage_verified_workload_release(db, **kwargs)

    assert calls == [(db, owner, 4)]
    assert db.flush_count == 0
    assert owner.ownership_state == "unresolved"
    assert all(
        reservation.reservation_state == "unresolved"
        for reservation in reservations
    )


def test_locked_validator_runs_before_release_mutations():
    db, owner, reservations, kwargs = scenario("unresolved")
    observed = []

    def inspect_locked_records(session, locked_ownership):
        observed.append(
            (
                len(session.reads),
                locked_ownership.ownership_state,
                tuple(item.reservation_state for item in reservations),
            )
        )

    kwargs["validate_under_locks"] = inspect_locked_records
    stage_verified_workload_release(db, **kwargs)

    assert observed == [
        (4, "unresolved", ("unresolved", "unresolved"))
    ]
    assert db.flush_count == 1
    assert owner.ownership_state == "released"


def test_invalid_locked_validator_preserves_capacity():
    db, owner, reservations, kwargs = scenario("unresolved")
    kwargs["validate_under_locks"] = True

    with pytest.raises(ValueError, match="Invalid locked"):
        stage_verified_workload_release(db, **kwargs)

    assert db.flush_count == 0
    assert owner.ownership_state == "unresolved"
    assert all(
        reservation.reservation_state == "unresolved"
        for reservation in reservations
    )
