"""Internal, fail-closed execution connection authorization staging.

This module is not integrated with routes, workers, source measurement,
or runtime admission. The caller owns the database transaction.

This internal staging service validates locked ownership, the
registered connection, and current PostgreSQL destination policy.
It stages non-secret evidence without committing the transaction.
"""

from datetime import datetime, timezone
from uuid import UUID

from app.models.data_quality_execution_connection_authorization import (
    DataQualityExecutionConnectionAuthorization,
)
from app.models.data_quality_workload_ownership import (
    DataQualityWorkloadOwnership,
)
from app.services.postgresql_execution_authorization import (
    PostgreSQLExecutionConnectionSnapshot,
    revalidate_postgresql_execution_connection,
)


class ExecutionConnectionAuthorizationStagingUnavailableError(RuntimeError):
    """Connection authorization evidence staging remains unavailable."""


def stage_execution_connection_authorization(
    db,
    *,
    execution_id: UUID,
    project_id: UUID,
    data_source_id: UUID,
    snapshot: PostgreSQLExecutionConnectionSnapshot,
):
    """Validate authorization and stage evidence in the caller's transaction.

    Locks ownership and registered connection identity, rechecks
    destination policy, and flushes one non-secret evidence record.
    Does not commit, rollback, retry, or access a client source.
    """
    if not isinstance(execution_id, UUID):
        raise ValueError("A valid execution UUID is required.")

    if not isinstance(project_id, UUID):
        raise ValueError("A valid project UUID is required.")

    if not isinstance(data_source_id, UUID):
        raise ValueError("A valid data source UUID is required.")

    if not isinstance(snapshot, PostgreSQLExecutionConnectionSnapshot):
        raise ValueError("A trusted PostgreSQL snapshot is required.")

    ownership = (
        db.query(DataQualityWorkloadOwnership)
        .filter(
            DataQualityWorkloadOwnership.execution_id == execution_id
        )
        .with_for_update()
        .one_or_none()
    )

    if ownership is None:
        raise ValueError("Execution workload ownership is missing.")

    if (
        ownership.execution_id != execution_id
        or ownership.project_id != project_id
        or ownership.data_source_id != data_source_id
    ):
        raise ValueError("Execution workload ownership identity mismatch.")

    if ownership.ownership_state != "reserved":
        raise ValueError("Execution workload ownership is not reserved.")

    if (
        ownership.released_at is not None
        or ownership.release_actor is not None
        or ownership.release_reason is not None
        or ownership.release_evidence_reference is not None
    ):
        raise ValueError("Reserved workload has release-audit information.")

    current_identity = revalidate_postgresql_execution_connection(
        db,
        data_source_id=data_source_id,
        expected_host=snapshot.host,
        expected_port=snapshot.port,
        expected_database=snapshot.database,
        expected_revision=snapshot.connection_revision,
    )

    # Policy is checked after the registered identity is locked.
    # These imports also allow tests to replace policy operations
    # without performing DNS lookups or certificate-file reads.
    from app.core.config import settings
    from app.services import postgresql_verification_policy as policy

    policy.require_postgresql_verification_configuration(settings)

    policy.require_approved_postgresql_destination(
        host=current_identity.host,
        port=current_identity.port,
        allowed_destinations=(
            settings.postgresql_verification_allowed_destinations
        ),
    )

    policy.require_postgresql_trusted_ca_file(
        settings.postgresql_verification_ssl_root_cert
    )

    approved_ip = policy.resolve_approved_postgresql_ip(
        host=current_identity.host,
        port=current_identity.port,
        allowed_networks=(
            settings.postgresql_verification_allowed_ip_networks
        ),
    )

    if (
        not isinstance(snapshot.host_address, str)
        or not snapshot.host_address
        or approved_ip != snapshot.host_address
    ):
        raise policy.PostgreSQLVerificationPolicyError(
            "Approved PostgreSQL IP no longer matches the snapshot."
        )

    # Store only approved, non-secret destination evidence.
    # The execution ID is the database primary key: duplicates
    # must fail at flush rather than overwrite prior evidence.
    evidence = DataQualityExecutionConnectionAuthorization(
        execution_id=execution_id,
        project_id=project_id,
        data_source_id=data_source_id,
        connection_revision=snapshot.connection_revision,
        authorized_host=current_identity.host,
        authorized_port=current_identity.port,
        authorized_database=current_identity.database_name,
        authorized_ip=approved_ip,
        authorized_at=datetime.now(timezone.utc),
    )

    # Transaction ownership belongs exclusively to the caller.
    # Never commit, rollback, retry, merge, or delete here.
    db.add(evidence)
    db.flush()

    return evidence
