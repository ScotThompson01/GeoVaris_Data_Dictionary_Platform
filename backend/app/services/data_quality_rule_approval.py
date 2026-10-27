"""Controlled approval of Data Quality rule versions.

Approval requires explicit project permission, separation of duties,
and a transactional audit event. Approval does not activate a rule.
"""

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.data_quality_rule import DataQualityRule
from app.models.data_field import DataField
from app.models.source_object import SourceObject
from app.models.data_source import DataSource
from app.models.data_quality_rule_version import DataQualityRuleVersion
from app.models.data_quality_rule_audit_event import DataQualityRuleAuditEvent
from app.services.project_authorization import require_dq_rule_approver


def approve_dq_rule_version(
    db: Session,
    *,
    project_id: uuid.UUID,
    rule_id: uuid.UUID,
    version_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> DataQualityRuleVersion:
    """Approve a draft version without activating its parent rule."""
    require_dq_rule_approver(
        db,
        user_id=actor_user_id,
        project_id=project_id,
    )

    authorized_rule_id = db.scalar(
        select(DataQualityRule.id)
        .join(DataField, DataQualityRule.data_field_id == DataField.id)
        .join(SourceObject, DataField.source_object_id == SourceObject.id)
        .join(DataSource, SourceObject.data_source_id == DataSource.id)
        .where(
            DataQualityRule.id == rule_id,
            DataSource.project_id == project_id,
        )
    )

    if authorized_rule_id is None:
        raise HTTPException(
            status_code=404,
            detail="Data Quality rule version not found.",
        )

    parent_rule = db.scalar(
        select(DataQualityRule)
        .where(DataQualityRule.id == rule_id)
        .with_for_update()
    )

    if parent_rule is None:
        raise HTTPException(
            status_code=404,
            detail="Data Quality rule version not found.",
        )

    version = db.scalar(
        select(DataQualityRuleVersion)
        .where(
            DataQualityRuleVersion.id == version_id,
            DataQualityRuleVersion.rule_id == rule_id,
        )
        .with_for_update()
    )

    if version is None:
        raise HTTPException(
            status_code=404,
            detail="Data Quality rule version not found.",
        )

    if parent_rule.status not in ("draft", "active"):
        raise HTTPException(
            status_code=409,
            detail="Only draft or active rules can receive approvals.",
        )

    if version.status != "draft":
        raise HTTPException(
            status_code=409,
            detail="Only draft rule versions can be approved.",
        )

    if version.created_by_user_id is None:
        raise HTTPException(
            status_code=409,
            detail="Rule version creator must be identified before approval.",
        )

    if version.created_by_user_id == actor_user_id:
        raise HTTPException(
            status_code=403,
            detail="Rule creators cannot approve their own versions.",
        )

    version.status = "approved"

    db.add(
        DataQualityRuleAuditEvent(
            id=uuid.uuid4(),
            project_id=project_id,
            actor_user_id=actor_user_id,
            rule_id=rule_id,
            version_id=version_id,
            event_type="version.approved",
            old_status="draft",
            new_status="approved",
        )
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return version
