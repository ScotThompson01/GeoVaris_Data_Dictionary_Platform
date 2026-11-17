"""Fail-closed assessment of connection-authorization failures.

Internal Phase 5E policy only. Not connected to runtime admission,
protected start, workers, source measurement, or recovery transactions.

The caller must independently establish transaction evidence. A missing
authorization record does not prove that an uncertain commit rolled back.
This policy never performs database work or authorizes corrective actions.
"""

from typing import TypedDict


class ConnectionAuthorizationFailureAssessment(TypedDict):
    disposition: str
    authorization_commit_evidence: bool | None
    protected_start_allowed: bool
    source_measurement_allowed: bool
    automatic_retry_allowed: bool
    capacity_release_allowed: bool


def assess_connection_authorization_failure(
    *,
    admission_committed: bool,
    authorization_committed: bool | None,
) -> ConnectionAuthorizationFailureAssessment:
    """Classify an authorization failure after verified committed admission.

    ``False`` must mean independently verified non-commit evidence, not
    merely a missing record or an exception during commit.

    ``None`` represents an unknown transaction outcome. Neither state
    authorizes advancing execution or releasing its reservation.

    Successful authorization is outside this failure-only policy.
    """
    if type(admission_committed) is not bool or not admission_committed:
        raise ValueError(
            "Verified committed admission is required for this assessment."
        )

    if authorization_committed is not None and type(
        authorization_committed
    ) is not bool:
        raise ValueError(
            "Authorization commit evidence must be boolean or None."
        )

    if authorization_committed is True:
        raise ValueError(
            "Successful authorization is outside the failure assessment."
        )

    return {
        "disposition": "manual_review_required",
        "authorization_commit_evidence": authorization_committed,
        "protected_start_allowed": False,
        "source_measurement_allowed": False,
        "automatic_retry_allowed": False,
        "capacity_release_allowed": False,
    }
