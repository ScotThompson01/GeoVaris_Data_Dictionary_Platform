"""Offline tests for fail-closed connection authorization failure assessment."""

import pytest

from app.services.data_quality_execution_connection_authorization_failure_policy import (
    assess_connection_authorization_failure,
)


FORBIDDEN_ACTIONS = (
    "protected_start_allowed",
    "source_measurement_allowed",
    "automatic_retry_allowed",
    "capacity_release_allowed",
)


@pytest.mark.parametrize("authorization_committed", [False, None])
def test_authorization_failure_requires_manual_review(authorization_committed):
    result = assess_connection_authorization_failure(
        admission_committed=True,
        authorization_committed=authorization_committed,
    )

    assert result["disposition"] == "manual_review_required"
    assert result["authorization_commit_evidence"] is authorization_committed
    assert set(result) == {
        "disposition",
        "authorization_commit_evidence",
        *FORBIDDEN_ACTIONS,
    }


@pytest.mark.parametrize("authorization_committed", [False, None])
@pytest.mark.parametrize("action", FORBIDDEN_ACTIONS)
def test_authorization_failure_never_permits_protected_actions(
    authorization_committed, action
):
    result = assess_connection_authorization_failure(
        admission_committed=True,
        authorization_committed=authorization_committed,
    )

    assert result[action] is False
    assert type(result[action]) is bool


@pytest.mark.parametrize(
    "invalid_admission",
    [False, None, 0, 1, "True", "False", [], {}, 1.0],
)
@pytest.mark.parametrize("authorization_committed", [False, None, True])
def test_invalid_or_unverified_admission_rejected(
    invalid_admission, authorization_committed
):
    with pytest.raises(ValueError):
        assess_connection_authorization_failure(
            admission_committed=invalid_admission,
            authorization_committed=authorization_committed,
        )


@pytest.mark.parametrize(
    "invalid_evidence",
    [0, 1, -1, 0.0, 1.0, "False", "None", "", [], {}, object()],
)
def test_malformed_authorization_commit_evidence_rejected(invalid_evidence):
    with pytest.raises(ValueError):
        assess_connection_authorization_failure(
            admission_committed=True,
            authorization_committed=invalid_evidence,
        )


def test_successful_authorization_is_not_a_failure_assessment():
    with pytest.raises(ValueError):
        assess_connection_authorization_failure(
            admission_committed=True,
            authorization_committed=True,
        )


def test_result_is_fresh_and_cannot_alter_subsequent_assessments():
    first = assess_connection_authorization_failure(
        admission_committed=True,
        authorization_committed=None,
    )

    first["disposition"] = "changed"
    for action in FORBIDDEN_ACTIONS:
        first[action] = True

    second = assess_connection_authorization_failure(
        admission_committed=True,
        authorization_committed=None,
    )

    assert first is not second
    assert second["disposition"] == "manual_review_required"
    assert second["authorization_commit_evidence"] is None
    assert all(second[action] is False for action in FORBIDDEN_ACTIONS)


def test_verified_noncommit_and_unknown_commit_remain_distinct():
    verified_noncommit = assess_connection_authorization_failure(
        admission_committed=True,
        authorization_committed=False,
    )
    unknown_commit = assess_connection_authorization_failure(
        admission_committed=True,
        authorization_committed=None,
    )

    assert verified_noncommit["authorization_commit_evidence"] is False
    assert unknown_commit["authorization_commit_evidence"] is None
    assert verified_noncommit["disposition"] == "manual_review_required"
    assert unknown_commit["disposition"] == "manual_review_required"
    assert all(
        verified_noncommit[action] is False
        and unknown_commit[action] is False
        for action in FORBIDDEN_ACTIONS
    )
