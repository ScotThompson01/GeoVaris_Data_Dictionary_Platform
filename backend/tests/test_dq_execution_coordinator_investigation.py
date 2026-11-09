"""Offline ambiguous-commit investigation contract tests.

Observations are supplied by an independently authorized investigator.
No database connection, source I/O, retry, or capacity release occurs.
"""

from uuid import uuid4

import pytest

from app.services.data_quality_execution_coordinator_investigation import (
    assess_ambiguous_commit_investigation,
)


@pytest.mark.parametrize(
    "observation",
    ["found", "not_found", "unavailable"],
)
def test_unknown_admission_commit_always_requires_review(observation):
    result = assess_ambiguous_commit_investigation(
        phase="admission",
        admission_committed=None,
        running_committed=False,
        execution_observation=observation,
    )

    assert result["disposition"] == "manual_review_required"
    assert result["execution_observation"] == observation
    assert result["automatic_retry_allowed"] is False
    assert result["capacity_release_allowed"] is False
    assert result["source_measurement_allowed"] is False


@pytest.mark.parametrize(
    "observation",
    ["found", "not_found", "unavailable"],
)
def test_unknown_running_commit_always_requires_review(observation):
    result = assess_ambiguous_commit_investigation(
        phase="before_running",
        admission_committed=True,
        running_committed=None,
        execution_observation=observation,
    )

    assert result["disposition"] == "manual_review_required"
    assert result["automatic_retry_allowed"] is False
    assert result["capacity_release_allowed"] is False
    assert result["source_measurement_allowed"] is False


@pytest.mark.parametrize(
    "invalid",
    [None, "", "committed", True, False, 1],
)
def test_invalid_observation_rejected(invalid):
    with pytest.raises(ValueError):
        assess_ambiguous_commit_investigation(
            phase="admission",
            admission_committed=None,
            running_committed=False,
            execution_observation=invalid,
        )


def test_verified_rollback_is_not_ambiguous_commit():
    with pytest.raises(ValueError):
        assess_ambiguous_commit_investigation(
            phase="admission",
            admission_committed=False,
            running_committed=False,
            execution_observation="not_found",
        )


def test_inconsistent_commit_evidence_rejected():
    with pytest.raises(ValueError):
        assess_ambiguous_commit_investigation(
            phase="before_running",
            admission_committed=False,
            running_committed=True,
            execution_observation="found",
        )


def test_assessment_does_not_require_execution_identity():
    # An uncertain admission commit may fail before the caller
    # receives the new execution UUID. An investigation still needs
    # to preserve uncertainty without inventing an identity.
    result = assess_ambiguous_commit_investigation(
        phase="admission",
        admission_committed=None,
        running_committed=False,
        execution_observation="unavailable",
    )

    assert result["disposition"] == "manual_review_required"
    assert result["execution_observation"] == "unavailable"


@pytest.mark.parametrize(
    ("phase", "admission_committed", "running_committed"),
    [
        ("before_running", None, False),
        ("before_measurement", True, None),
        ("measurement", True, None),
        ("outcome_recording", True, None),
    ],
)
@pytest.mark.parametrize(
    "observation",
    ["found", "not_found", "unavailable"],
)
def test_all_remaining_allowed_unknown_commit_states_require_review(
    phase,
    admission_committed,
    running_committed,
    observation,
):
    result = assess_ambiguous_commit_investigation(
        phase=phase,
        admission_committed=admission_committed,
        running_committed=running_committed,
        execution_observation=observation,
    )

    assert result["disposition"] == "manual_review_required"
    assert result["execution_observation"] == observation
    assert result["automatic_retry_allowed"] is False
    assert result["capacity_release_allowed"] is False
    assert result["source_measurement_allowed"] is False


@pytest.mark.parametrize(
    ("phase", "admission_committed", "running_committed"),
    [
        ("admission", True, None),
        ("before_running", False, None),
        ("before_measurement", None, True),
        ("measurement", True, False),
        ("outcome_recording", None, None),
        ("outcome_committed", True, None),
        ("unknown_phase", None, False),
        ("admission", 1, False),
        ("before_running", True, 0),
    ],
)
def test_unsupported_unknown_commit_evidence_fails_closed(
    phase,
    admission_committed,
    running_committed,
):
    with pytest.raises(ValueError):
        assess_ambiguous_commit_investigation(
            phase=phase,
            admission_committed=admission_committed,
            running_committed=running_committed,
            execution_observation="unavailable",
        )
