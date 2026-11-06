"""Fail-closed recovery assessment tests for Phase 5E.

No database operations, client-source measurements, state transitions,
or capacity releases are authorized by this policy.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.data_quality_execution_recovery_policy import (
    assess_protected_execution_recovery,
)


def protected_fixture(*, execution_status="running", state="reserved"):
    ownership_id = uuid4()
    source_id = uuid4()

    execution = SimpleNamespace(
        id=uuid4(),
        status=execution_status,
    )
    ownership = SimpleNamespace(
        id=ownership_id,
        execution_id=execution.id,
        data_source_id=source_id,
        ownership_state=state,
        released_at=None,
        release_actor=None,
        release_reason=None,
        release_evidence_reference=None,
    )

    reservations = [
        SimpleNamespace(
            id=uuid4(),
            ownership_id=ownership_id,
            ownership_data_source_id=source_id,
            data_source_id=source_data,
            capacity_control_id=uuid4(),
            reservation_scope=scope,
            reservation_state=state,
            released_at=None,
            release_actor=None,
            release_reason=None,
            release_evidence_reference=None,
        )
        for scope, source_data in (
            ("installation", None),
            ("source", source_id),
        )
    ]

    return execution, ownership, reservations


@pytest.mark.parametrize(
    "status",
    ["pending", "running", "status_uncertain",
     "failed", "incomplete", "succeeded", "cancelled"],
)
def test_interruption_requires_manual_review_for_any_execution_status(status):
    execution, ownership, reservations = protected_fixture(
        execution_status=status
    )

    result = assess_protected_execution_recovery(
        execution=execution,
        ownership=ownership,
        reservations=reservations,
        interruption_detected=True,
    )

    assert result == "manual_review_required"


def test_no_interruption_signal_does_not_infer_a_crash():
    execution, ownership, reservations = protected_fixture()

    result = assess_protected_execution_recovery(
        execution=execution,
        ownership=ownership,
        reservations=reservations,
        interruption_detected=False,
    )

    assert result == "no_recovery_action"


@pytest.mark.parametrize("state", ["reserved", "unresolved"])
def test_recovery_assessment_preserves_existing_protection(state):
    execution, ownership, reservations = protected_fixture(state=state)

    before = (
        dict(vars(execution)),
        dict(vars(ownership)),
        [dict(vars(item)) for item in reservations],
    )

    result = assess_protected_execution_recovery(
        execution=execution,
        ownership=ownership,
        reservations=reservations,
        interruption_detected=True,
    )

    after = (
        dict(vars(execution)),
        dict(vars(ownership)),
        [dict(vars(item)) for item in reservations],
    )

    assert result == "manual_review_required"
    assert after == before


def test_missing_reservation_fails_closed():
    execution, ownership, reservations = protected_fixture()

    with pytest.raises(ValueError):
        assess_protected_execution_recovery(
            execution=execution,
            ownership=ownership,
            reservations=reservations[:1],
            interruption_detected=True,
        )


def test_mismatched_reservation_state_fails_closed():
    execution, ownership, reservations = protected_fixture()
    reservations[1].reservation_state = "released"

    with pytest.raises(ValueError):
        assess_protected_execution_recovery(
            execution=execution,
            ownership=ownership,
            reservations=reservations,
            interruption_detected=True,
        )


def test_invalid_interruption_signal_fails_closed():
    execution, ownership, reservations = protected_fixture()

    with pytest.raises(ValueError, match="interruption"):
        assess_protected_execution_recovery(
            execution=execution,
            ownership=ownership,
            reservations=reservations,
            interruption_detected="unknown",
        )


def test_mismatched_execution_identity_fails_closed():
    execution, ownership, reservations = protected_fixture()
    ownership.execution_id = uuid4()

    with pytest.raises(
        ValueError,
        match="Execution and workload ownership identity mismatch",
    ):
        assess_protected_execution_recovery(
            execution=execution,
            ownership=ownership,
            reservations=reservations,
            interruption_detected=True,
        )
