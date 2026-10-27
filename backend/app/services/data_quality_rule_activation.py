"""Controlled activation of approved Data Quality rule versions."""

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.data_field import DataField
from app.models.data_quality_rule import DataQualityRule
from app.models.data_quality_rule_audit_event import DataQualityRuleAuditEvent
from app.models.data_quality_rule_version import DataQualityRuleVersion
from app.models.data_source import DataSource
from app.models.source_object import SourceObject
from app.services.project_authorization import require_dq_rule_approver


def activate_dq_rule_version(
    db: Session,
    *,
    project_id: uuid.UUID,
    rule_id: uuid.UUID,
    version_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> DataQualityRule:
    """Activate an approved version and record the change atomically."""
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
            detail="Retired rules cannot be activated.",
        )

    if version.status != "approved":
        raise HTTPException(
            status_code=409,
            detail="Only approved rule versions can be activated.",
        )

    if (
        parent_rule.status == "active"
        and parent_rule.active_version_id == version_id
    ):
        raise HTTPException(
            status_code=409,
            detail="This rule version is already active.",
        )

    previous_status = parent_rule.status
    parent_rule.status = "active"
    parent_rule.active_version_id = version_id

    db.add(
        DataQualityRuleAuditEvent(
            id=uuid.uuid4(),
            project_id=project_id,
            actor_user_id=actor_user_id,
            rule_id=rule_id,
            version_id=version_id,
            event_type="version.activated",
            old_status=previous_status,
            new_status="active",
        )
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return parent_rule
