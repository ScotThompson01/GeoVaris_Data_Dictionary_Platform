"""Independent read-only protection verification for Phase 5E.

Internal-only service. NOT connected to API routes, workers, source
measurements, or runtime admission.

The session factory must open an independent session, not reuse the
admission or RUNNING transaction session.

A successful inspection establishes visibility at the time of the
query. It does not prove transaction history, authorize source
measurement, or prevent subsequent changes to protection records.
"""

from uuid import UUID

from app.services.data_quality_execution_coordinator_protection_snapshot import (
    inspect_protected_execution_snapshot,
)


def verify_committed_protection(
    *,
    session_factory,
    project_id: UUID,
    execution_id: UUID,
    expected_status: str,
) -> UUID:
    """Inspect protection in a fresh session and return only the execution ID."""
    if not callable(session_factory):
        raise ValueError("A callable session factory is required.")

    if (
        not isinstance(project_id, UUID)
        or not isinstance(execution_id, UUID)
    ):
        raise ValueError("Invalid protected execution identity.")

    if expected_status not in ("pending", "running"):
        raise ValueError("Invalid expected execution status.")

    db = session_factory()

    try:
        execution = inspect_protected_execution_snapshot(
            db,
            project_id=project_id,
            execution_id=execution_id,
            expected_status=expected_status,
        )

        if (
            not isinstance(getattr(execution, "id", None), UUID)
            or execution.id != execution_id
            or getattr(execution, "project_id", None) != project_id
            or getattr(execution, "status", None) != expected_status
        ):
            raise ValueError(
                "Committed protection snapshot identity mismatch."
            )

        return execution_id

    finally:
        db.close()
