"""API endpoints for field-level Data Quality rules."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.db.session import get_db
from app.models.data_field import DataField
from app.models.source_object import SourceObject
from app.models.data_source import DataSource
from app.models.data_quality_rule import DataQualityRule
from app.models.data_quality_rule_version import DataQualityRuleVersion
from app.schemas.data_quality_rule import (
    RangeRuleCreate,
    RangeRuleCreateResponse,
    RangeRuleRead,
    RangeRuleVersionRead,
)
from app.services.project_authorization import require_project_access

router = APIRouter()


@router.post("", status_code=201, response_model=RangeRuleCreateResponse)
def create_draft_range_rule(
    payload: RangeRuleCreate,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    """Create an authorized, unapproved range rule and its first version."""
    data_field = db.get(DataField, payload.data_field_id)
    if data_field is None:
        raise HTTPException(status_code=404, detail="Data field not found.")

    source_object = db.get(SourceObject, data_field.source_object_id)
    if source_object is None:
        raise HTTPException(status_code=404, detail="Data field not found.")

    data_source = db.get(DataSource, source_object.data_source_id)
    if data_source is None:
        raise HTTPException(status_code=404, detail="Data field not found.")

    try:
        require_project_access(
            db,
            user_id=session.user.id,
            project_id=data_source.project_id,
        )
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        raise HTTPException(
            status_code=404,
            detail="Data field not found.",
        ) from exc

    rule = DataQualityRule(
        id=uuid.uuid4(),
        data_field_id=payload.data_field_id,
        rule_name=payload.rule_name,
        status="draft",
        active_version_id=None,
    )
    version = DataQualityRuleVersion(
        id=uuid.uuid4(),
        rule_id=rule.id,
        version_number=1,
        rule_type=payload.rule_type,
        quality_dimension=payload.quality_dimension,
        min_value=payload.min_value,
        max_value=payload.max_value,
        null_allowed=payload.null_allowed,
        status="draft",
    )

    try:
        db.add(rule)
        db.flush()
        version.rule_id = rule.id
        db.add(version)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return RangeRuleCreateResponse(
        rule_id=rule.id,
        version_id=version.id,
        data_field_id=rule.data_field_id,
        version_number=1,
        rule_status="draft",
        version_status="draft",
        active_version_id=None,
    )




@router.get("", response_model=list[RangeRuleRead])
def list_field_range_rules(
    data_field_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    """List versioned rules for a field in an authorized project."""
    data_field = db.get(DataField, data_field_id)
    if data_field is None:
        raise HTTPException(status_code=404, detail="Data field not found.")

    source_object = db.get(SourceObject, data_field.source_object_id)
    if source_object is None:
        raise HTTPException(status_code=404, detail="Data field not found.")

    data_source = db.get(DataSource, source_object.data_source_id)
    if data_source is None:
        raise HTTPException(status_code=404, detail="Data field not found.")

    try:
        require_project_access(
            db,
            user_id=session.user.id,
            project_id=data_source.project_id,
        )
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        raise HTTPException(
            status_code=404,
            detail="Data field not found.",
        ) from exc

    rules = db.scalars(
        select(DataQualityRule)
        .where(DataQualityRule.data_field_id == data_field_id)
        .order_by(DataQualityRule.rule_name, DataQualityRule.id)
    ).all()

    results = []

    for rule in rules:
        versions = db.scalars(
            select(DataQualityRuleVersion)
            .where(DataQualityRuleVersion.rule_id == rule.id)
            .order_by(DataQualityRuleVersion.version_number)
        ).all()

        results.append(
            RangeRuleRead(
                rule_id=rule.id,
                data_field_id=rule.data_field_id,
                rule_name=rule.rule_name,
                status=rule.status,
                active_version_id=rule.active_version_id,
                versions=[
                    RangeRuleVersionRead(
                        version_id=version.id,
                        version_number=version.version_number,
                        rule_type=version.rule_type,
                        quality_dimension=version.quality_dimension,
                        min_value=version.min_value,
                        max_value=version.max_value,
                        null_allowed=version.null_allowed,
                        status=version.status,
                    )
                    for version in versions
                ],
            )
        )

    return results
