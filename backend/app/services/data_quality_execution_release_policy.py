"""Fail-closed release eligibility policy for Phase 5E.

This module does not access databases, contact sources, authorize users,
change execution states, or release capacity. Evidence assertions must
come from independently verified, trusted application workflows.
"""

from enum import Enum


class ReleaseEvidenceType(str, Enum):
    VERIFIED_SOURCE_TERMINATION = "verified_source_termination"
    AUTHORIZED_ADMIN_RESOLUTION = "authorized_admin_resolution"


def validate_release_evidence(
    *,
    evidence_type: ReleaseEvidenceType,
    actor: str,
    reason: str,
    evidence_reference: str,
    source_termination_verified: bool,
    administrator_authorized: bool,
) -> None:
    """Validate independently established release prerequisites.

    Successful validation does not itself authorize or perform release.
    """

    if not isinstance(evidence_type, ReleaseEvidenceType):
        raise ValueError("Unknown release evidence type.")

    for name, value in (
        ("actor", actor),
        ("reason", reason),
        ("evidence_reference", evidence_reference),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Release {name} is required.")

    if type(source_termination_verified) is not bool:
        raise ValueError("Invalid source termination verification flag.")

    if type(administrator_authorized) is not bool:
        raise ValueError("Invalid administrator authorization flag.")

    if evidence_type is ReleaseEvidenceType.VERIFIED_SOURCE_TERMINATION:
        if source_termination_verified is not True:
            raise ValueError("Verified source termination is required.")

    elif evidence_type is ReleaseEvidenceType.AUTHORIZED_ADMIN_RESOLUTION:
        if administrator_authorized is not True:
            raise ValueError("Administrator authorization is required.")
