"""Fail-closed consistency checks for proposed workload release evidence.

This module only checks record consistency. It does NOT authenticate actors,
verify source termination, prove evidence provenance, or authorize release.
Do not use successful validation as a release permission.
"""

from datetime import datetime
from uuid import UUID

from app.services.data_quality_execution_release_policy import ReleaseEvidenceType


def _valid_uuid(value):
    return isinstance(value, UUID)


def _valid_text(value, limit):
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= limit
    )


def _aware_datetime(value):
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def validate_release_evidence_record_consistency(
    *,
    evidence,
    ownership,
    resolution_grant=None,
) -> None:
    """Reject inconsistent evidence, ownership, and grant snapshots.

    Snapshot consistency is necessary but insufficient for release.
    Grant revocation and authorization must be rechecked transactionally.
    """

    if evidence is None or ownership is None:
        raise ValueError("Evidence and workload ownership are required.")

    for name in ("id", "ownership_id", "project_id",
                 "data_source_id", "actor_user_id"):
        if not _valid_uuid(getattr(evidence, name, None)):
            raise ValueError(f"Invalid evidence {name}.")

    for name in ("id", "project_id", "data_source_id"):
        if not _valid_uuid(getattr(ownership, name, None)):
            raise ValueError(f"Invalid workload {name}.")

    for evidence_field, ownership_field in (
        ("ownership_id", "id"),
        ("project_id", "project_id"),
        ("data_source_id", "data_source_id"),
    ):
        if getattr(evidence, evidence_field) != getattr(
            ownership, ownership_field
        ):
            raise ValueError("Evidence workload identity mismatch.")

    if getattr(ownership, "ownership_state", None) not in (
        "reserved", "unresolved"
    ):
        raise ValueError("Workload is not protected.")

    if not _valid_text(getattr(evidence, "reason", None), 1000):
        raise ValueError("Evidence reason is invalid.")

    if not _valid_text(
        getattr(evidence, "evidence_reference", None), 1000
    ):
        raise ValueError("Evidence reference is invalid.")

    if not _aware_datetime(getattr(evidence, "created_at", None)):
        raise ValueError("Evidence creation timestamp is invalid.")

    status = getattr(evidence, "evidence_status", None)
    if status != "confirmed":
        raise ValueError("Evidence has not been confirmed.")

    if not _valid_uuid(getattr(evidence, "verified_by_user_id", None)):
        raise ValueError("Evidence reviewer is invalid.")

    verified_at = getattr(evidence, "verified_at", None)
    if not _aware_datetime(verified_at):
        raise ValueError("Evidence review timestamp is invalid.")

    if verified_at < evidence.created_at:
        raise ValueError("Evidence review precedes its creation.")

    evidence_type = getattr(evidence, "evidence_type", None)
    if evidence_type == ReleaseEvidenceType.VERIFIED_SOURCE_TERMINATION.value:
        if (
            getattr(evidence, "resolution_grant_id", None) is not None
            or resolution_grant is not None
        ):
            raise ValueError(
                "Termination evidence cannot use an administrator grant."
            )
    elif evidence_type == ReleaseEvidenceType.AUTHORIZED_ADMIN_RESOLUTION.value:
        if resolution_grant is None:
            raise ValueError("Administrator resolution grant is required.")

        for name in ("id", "project_id", "user_id",
                     "granted_by_user_id"):
            if not _valid_uuid(getattr(resolution_grant, name, None)):
                raise ValueError(f"Invalid resolution grant {name}.")

        if (
            evidence.resolution_grant_id != resolution_grant.id
            or evidence.project_id != resolution_grant.project_id
            or evidence.actor_user_id != resolution_grant.user_id
        ):
            raise ValueError("Resolution grant identity mismatch.")

        if not _aware_datetime(
            getattr(resolution_grant, "created_at", None)
        ):
            raise ValueError("Resolution grant timestamp is invalid.")

        if resolution_grant.created_at > evidence.created_at:
            raise ValueError("Resolution grant postdates the evidence.")

        if getattr(resolution_grant, "revoked_at", None) is not None:
            raise ValueError("Resolution grant is revoked.")
    else:
        raise ValueError("Unknown release evidence type.")
