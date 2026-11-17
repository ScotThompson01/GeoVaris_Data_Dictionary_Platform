"""Standalone commit-and-verify coordinator for connection authorization.

Internal Phase 5E component only. Not wired into protected start, runtime
admission, API routes, workers, or client-source measurement.

Commit exceptions preserve their original uncertainty. A later missing
evidence row is not proof of rollback. No automatic retry, capacity release,
or recovery operation is performed here.
"""

from uuid import UUID

from app.services.data_quality_execution_connection_authorization import (
    stage_execution_connection_authorization,
)
from app.services.data_quality_execution_committed_connection_authorization import (
    verify_committed_connection_authorization,
)
from app.services.data_quality_execution_coordinator_transaction import (
    run_coordinator_transaction,
)
from app.services.postgresql_execution_authorization import (
    PostgreSQLExecutionConnectionSnapshot,
)


def commit_and_verify_connection_authorization(
    *,
    session_factory,
    execution_id: UUID,
    project_id: UUID,
    data_source_id: UUID,
    snapshot: PostgreSQLExecutionConnectionSnapshot,
) -> UUID:
    """Commit staged authorization, then independently inspect its evidence.

    A successful result establishes only matching evidence visibility
    at verification time. It does not authorize protected start or source
    measurement and does not guarantee the connection remains valid.
    """
    if not callable(session_factory):
        raise ValueError("A callable session factory is required.")

    if (
        not isinstance(execution_id, UUID)
        or not isinstance(project_id, UUID)
        or not isinstance(data_source_id, UUID)
    ):
        raise ValueError("Valid authorization UUID identities are required.")

    if not isinstance(snapshot, PostgreSQLExecutionConnectionSnapshot):
        raise ValueError("A validated PostgreSQL snapshot is required.")

    revision = snapshot.connection_revision
    if type(revision) is not int or revision <= 0:
        raise ValueError("A positive connection revision is required.")

    def stage(db):
        evidence = stage_execution_connection_authorization(
            db,
            execution_id=execution_id,
            project_id=project_id,
            data_source_id=data_source_id,
            snapshot=snapshot,
        )

        # Validate before commit; never carry an ORM object out of this
        # transaction. An invalid result must block the commit.
        if (
            evidence is None
            or evidence.execution_id != execution_id
            or evidence.project_id != project_id
            or evidence.data_source_id != data_source_id
            or type(evidence.connection_revision) is not int
            or evidence.connection_revision != revision
        ):
            raise ValueError(
                "Staged connection authorization evidence does not match."
            )

        return execution_id

    # Owns commit, rollback on failure, and session closing. Any exception,
    # including an ambiguous commit outcome, propagates without retry.
    committed_id = run_coordinator_transaction(
        session_factory=session_factory,
        stage=stage,
    )

    if not isinstance(committed_id, UUID) or committed_id != execution_id:
        raise ValueError(
            "Committed authorization execution identity mismatch."
        )

    verified_id = verify_committed_connection_authorization(
        session_factory=session_factory,
        execution_id=execution_id,
        project_id=project_id,
        data_source_id=data_source_id,
        expected_connection_revision=revision,
    )

    if not isinstance(verified_id, UUID) or verified_id != execution_id:
        raise ValueError(
            "Verified authorization execution identity mismatch."
        )

    return execution_id
