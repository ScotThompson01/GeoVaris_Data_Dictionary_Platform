"""Validate persistent workload protection before any future release.

Pure validation only. This module does not authorize, commit, or
perform capacity release, and never contacts client data sources.
"""

from collections.abc import Sequence
from uuid import UUID


def validate_protected_workload(
    *,
    ownership,
    reservations: Sequence,
) -> None:
    """Reject incomplete, inconsistent, or already released protection."""

    if ownership is None:
        raise ValueError("Workload ownership is required.")

    ownership_id = getattr(ownership, "id", None)
    source_id = getattr(ownership, "data_source_id", None)
    state = getattr(ownership, "ownership_state", None)

    if not isinstance(ownership_id, UUID):
        raise ValueError("Invalid workload ownership identity.")

    if not isinstance(source_id, UUID):
        raise ValueError("Invalid workload source identity.")

    if state not in ("reserved", "unresolved"):
        raise ValueError("Workload is not actively protected.")

    if not isinstance(reservations, (list, tuple)) or len(reservations) != 2:
        raise ValueError("Exactly two capacity reservations are required.")

    by_scope = {}

    for reservation in reservations:
        if reservation is None:
            raise ValueError("Missing capacity reservation.")

        scope = getattr(reservation, "reservation_scope", None)

        if scope not in ("installation", "source") or scope in by_scope:
            raise ValueError("Invalid or duplicate reservation scope.")

        if getattr(reservation, "ownership_id", None) != ownership_id:
            raise ValueError("Reservation belongs to another workload.")

        if (
            getattr(reservation, "ownership_data_source_id", None)
            != source_id
        ):
            raise ValueError(
                "Reservation workload source identity mismatch."
            )

        if getattr(reservation, "reservation_state", None) != state:
            raise ValueError("Ownership and reservation states do not match.")

        if not isinstance(getattr(reservation, "capacity_control_id", None), UUID):
            raise ValueError("Invalid reservation capacity control.")

        if any(
            getattr(reservation, field, None) is not None
            for field in (
                "released_at",
                "release_actor",
                "release_reason",
                "release_evidence_reference",
            )
        ):
            raise ValueError("Protected reservation contains release evidence.")

        by_scope[scope] = reservation

    if set(by_scope) != {"installation", "source"}:
        raise ValueError("Installation and source reservations are required.")

    if by_scope["installation"].data_source_id is not None:
        raise ValueError("Installation reservation must not identify a source.")

    if by_scope["source"].data_source_id != source_id:
        raise ValueError("Source reservation does not match the workload.")

    if (
        by_scope["installation"].capacity_control_id
        == by_scope["source"].capacity_control_id
    ):
        raise ValueError("Reservations must use distinct capacity controls.")

    if any(
        getattr(ownership, field, None) is not None
        for field in (
            "released_at",
            "release_actor",
            "release_reason",
            "release_evidence_reference",
        )
    ):
        raise ValueError("Protected workload contains release evidence.")
