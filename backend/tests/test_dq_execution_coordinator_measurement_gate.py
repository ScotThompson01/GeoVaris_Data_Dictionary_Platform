"""Fail-closed prerequisites for Phase 5E source measurement.

The gate is internal and does not authorize, schedule, or perform
source I/O. Commit evidence must be independently verified.
"""

import pytest

from app.services.data_quality_execution_coordinator_measurement_gate import (
    require_committed_protected_start,
)


def test_both_confirmed_commits_pass_the_transaction_gate():
    assert require_committed_protected_start(
        admission_committed=True,
        running_committed=True,
    ) is None


@pytest.mark.parametrize(
    ("admission_committed", "running_committed"),
    [
        (False, False),
        (False, True),
        (False, None),
        (True, False),
        (True, None),
        (None, False),
        (None, True),
        (None, None),
    ],
)
def test_missing_failed_or_unknown_commit_blocks_measurement(
    admission_committed,
    running_committed,
):
    with pytest.raises(ValueError):
        require_committed_protected_start(
            admission_committed=admission_committed,
            running_committed=running_committed,
        )


@pytest.mark.parametrize(
    "invalid",
    [0, 1, "true", "", [], {}, object()],
)
def test_invalid_admission_commit_evidence_rejected(invalid):
    with pytest.raises(ValueError):
        require_committed_protected_start(
            admission_committed=invalid,
            running_committed=True,
        )


@pytest.mark.parametrize(
    "invalid",
    [0, 1, "true", "", [], {}, object()],
)
def test_invalid_running_commit_evidence_rejected(invalid):
    with pytest.raises(ValueError):
        require_committed_protected_start(
            admission_committed=True,
            running_committed=invalid,
        )


def test_commit_evidence_is_explicitly_required():
    with pytest.raises(TypeError):
        require_committed_protected_start()


def test_partial_commit_evidence_is_rejected():
    with pytest.raises(TypeError):
        require_committed_protected_start(
            admission_committed=True,
        )
