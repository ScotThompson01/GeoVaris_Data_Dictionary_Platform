"""Fail-closed transaction and interruption policy for Phase 5E.

No source I/O, database operations, worker activation, or capacity release.
"""

import pytest

from app.services.data_quality_execution_coordinator_failure_policy import (
    assess_coordinator_failure,
)


@pytest.mark.parametrize(
    ("phase", "admission_committed", "running_committed", "expected"),
    [
        ("admission", False, False, "rollback_uncommitted_admission"),
        ("before_running", True, False, "manual_review_required"),
        ("before_measurement", True, True, "manual_review_required"),
        ("measurement", True, True, "manual_review_required"),
        ("outcome_recording", True, True, "manual_review_required"),
        ("outcome_committed", True, True, "manual_review_required"),
    ],
)
def test_coordinator_failure_policy(
    phase,
    admission_committed,
    running_committed,
    expected,
):
    result = assess_coordinator_failure(
        phase=phase,
        admission_committed=admission_committed,
        running_committed=running_committed,
    )

    assert result == expected


@pytest.mark.parametrize(
    ("phase", "admission_committed", "running_committed"),
    [
        ("unknown", True, True),
        ("measurement", False, False),
        ("before_running", False, False),
        ("before_measurement", True, False),
        ("admission", True, False),
        ("admission", False, True),
    ],
)
def test_inconsistent_coordinator_state_rejected(
    phase,
    admission_committed,
    running_committed,
):
    with pytest.raises(ValueError):
        assess_coordinator_failure(
            phase=phase,
            admission_committed=admission_committed,
            running_committed=running_committed,
        )


@pytest.mark.parametrize(
    "invalid",
    [None, 0, 1, "true", [], {}],
)
def test_commit_evidence_must_be_boolean(invalid):
    with pytest.raises(ValueError):
        assess_coordinator_failure(
            phase="measurement",
            admission_committed=invalid,
            running_committed=True,
        )



@pytest.mark.parametrize(
    ("phase", "admission_committed", "running_committed"),
    [
        ("admission", None, False),
        ("before_running", None, False),
        ("before_running", True, None),
        ("before_measurement", True, None),
        ("measurement", True, None),
        ("outcome_recording", True, None),
    ],
)
def test_unknown_commit_outcome_requires_review(
    phase, admission_committed, running_committed
):
    assert assess_coordinator_failure(
        phase=phase,
        admission_committed=admission_committed,
        running_committed=running_committed,
    ) == "manual_review_required"


@pytest.mark.parametrize(
    ("phase", "admission_committed", "running_committed"),
    [
        ("measurement", None, True),
        ("outcome_recording", None, None),
        ("before_measurement", None, False),
        ("admission", None, True),
        ("before_running", False, None),
        ("measurement", True, False),
    ],
)
def test_ambiguous_or_contradictory_commit_evidence_fails_closed(
    phase, admission_committed, running_committed
):
    with pytest.raises(ValueError):
        assess_coordinator_failure(
            phase=phase,
            admission_committed=admission_committed,
            running_committed=running_committed,
        )

def test_running_commit_evidence_must_be_boolean():
    with pytest.raises(ValueError):
        assess_coordinator_failure(
            phase="measurement",
            admission_committed=True,
            running_committed="true",
        )
