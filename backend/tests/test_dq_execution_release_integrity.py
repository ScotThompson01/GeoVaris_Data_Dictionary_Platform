"""Tests for fail-closed workload release integrity validation."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.data_quality_execution_release_integrity import (
    validate_protected_workload,
)


def protected_workload(state="reserved"):
    owner_id = uuid4()
    source_id = uuid4()

    ownership = SimpleNamespace(
        id=owner_id,
        data_source_id=source_id,
        ownership_state=state,
        released_at=None,
        release_actor=None,
        release_reason=None,
        release_evidence_reference=None,
    )

    installation = SimpleNamespace(
        ownership_id=owner_id,
        capacity_control_id=uuid4(),
        reservation_scope="installation",
        reservation_state=state,
        data_source_id=None,
        released_at=None,
        release_actor=None,
        release_reason=None,
        release_evidence_reference=None,
    )

    source = SimpleNamespace(
        ownership_id=owner_id,
        capacity_control_id=uuid4(),
        reservation_scope="source",
        reservation_state=state,
        data_source_id=source_id,
        released_at=None,
        release_actor=None,
        release_reason=None,
        release_evidence_reference=None,
    )

    return ownership, [installation, source]


@pytest.mark.parametrize("state", ["reserved", "unresolved"])
def test_valid_protected_workload(state):
    ownership, reservations = protected_workload(state)
    validate_protected_workload(
        ownership=ownership,
        reservations=reservations,
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_reservation",
        "duplicate_scope",
        "wrong_owner",
        "wrong_source",
        "mismatched_state",
        "released_owner",
        "released_reservation",
        "unexpected_audit",
        "same_capacity_control",
    ],
)
def test_rejects_invalid_workload_protection(mutation):
    ownership, reservations = protected_workload()

    if mutation == "missing_reservation":
        reservations.pop()
    elif mutation == "duplicate_scope":
        reservations[1].reservation_scope = "installation"
    elif mutation == "wrong_owner":
        reservations[1].ownership_id = uuid4()
    elif mutation == "wrong_source":
        reservations[1].data_source_id = uuid4()
    elif mutation == "mismatched_state":
        reservations[1].reservation_state = "unresolved"
    elif mutation == "released_owner":
        ownership.ownership_state = "released"
    elif mutation == "released_reservation":
        reservations[1].reservation_state = "released"
    elif mutation == "unexpected_audit":
        reservations[0].release_actor = "unexpected"
    elif mutation == "same_capacity_control":
        reservations[1].capacity_control_id = reservations[0].capacity_control_id

    with pytest.raises(ValueError):
        validate_protected_workload(
            ownership=ownership,
            reservations=reservations,
        )


def test_rejects_missing_ownership():
    _, reservations = protected_workload()

    with pytest.raises(ValueError):
        validate_protected_workload(
            ownership=None,
            reservations=reservations,
        )
