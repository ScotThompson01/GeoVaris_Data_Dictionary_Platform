"""Internal transactional lookup of workload release evidence.

Not connected to runtime. This service validates persisted-record
consistency only. It does NOT verify source termination, authenticate
the caller, authorize capacity release, or commit a transaction.

Future integration must preserve the global capacity-control-first
lock order and revalidate authority in the release transaction.
"""

from uuid import UUID

from sqlalchemy import select

from app.models.data_quality_workload_ownership import (
    DataQualityWorkloadOwnership as Ownership,
)
from app.models.data_quality_workload_release_evidence import (
    DataQualityWorkloadReleaseEvidence as Evidence,
)
from app.models.data_quality_workload_resolution_grant import (
    DataQualityWorkloadResolutionGrant as Grant,
)
from app.models.project_access import ProjectAccess
from app.services.data_quality_workload_release_evidence_integrity import (
    validate_release_evidence_record_consistency,
)
from app.services.data_quality_execution_release_policy import (
    ReleaseEvidenceType,
)


def load_consistent_release_evidence(
    db,
    *,
    evidence_id: UUID,
    ownership_id: UUID,
    project_id: UUID,
    data_source_id: UUID,
):
    """Fetch and validate current records under caller-owned transaction.

    This function must not be used as a stand-alone release authorization.
    The caller must already have established a trusted actor identity.
    Do not call it before capacity-control locks in a release transaction.
    """

    for name, value in (
        ("evidence_id", evidence_id),
        ("ownership_id", ownership_id),
        ("project_id", project_id),
        ("data_source_id", data_source_id),
    ):
        if not isinstance(value, UUID):
            raise ValueError(f"Invalid {name}.")

    ownership = db.scalar(
        select(Ownership)
        .where(
            Ownership.id == ownership_id,
            Ownership.project_id == project_id,
            Ownership.data_source_id == data_source_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if ownership is None:
        raise ValueError("Protected workload ownership not found.")

    evidence = db.scalar(
        select(Evidence)
        .where(
            Evidence.id == evidence_id,
            Evidence.ownership_id == ownership_id,
            Evidence.project_id == project_id,
            Evidence.data_source_id == data_source_id,
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if evidence is None:
        raise ValueError("Scoped release evidence not found.")

    grant = None

    if (
        evidence.evidence_type
        == ReleaseEvidenceType.AUTHORIZED_ADMIN_RESOLUTION.value
    ):
        if not isinstance(evidence.actor_user_id, UUID):
            raise ValueError("Invalid evidence actor identity.")

        if not isinstance(evidence.resolution_grant_id, UUID):
            raise ValueError("Missing administrator resolution grant.")

        membership = db.scalar(
            select(ProjectAccess.id)
            .where(
                ProjectAccess.user_id == evidence.actor_user_id,
                ProjectAccess.project_id == project_id,
            )
            .with_for_update()
        )

        if membership is None:
            raise ValueError("Resolution actor lacks project membership.")

        grant = db.scalar(
            select(Grant)
            .where(
                Grant.id == evidence.resolution_grant_id,
                Grant.project_id == project_id,
                Grant.user_id == evidence.actor_user_id,
                Grant.revoked_at.is_(None),
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if grant is None:
            raise ValueError("Active administrator resolution grant not found.")

    validate_release_evidence_record_consistency(
        evidence=evidence,
        ownership=ownership,
        resolution_grant=grant,
    )

    return evidence
