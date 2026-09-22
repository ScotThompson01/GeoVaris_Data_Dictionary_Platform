import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.db.session import get_db
from app.models.data_field import DataField
from app.models.data_source import DataSource
from app.models.source_object import SourceObject
from app.schemas.dictionary import DictionaryFieldRead
from app.services.project_authorization import require_project_access

router = APIRouter()


@router.get(
    "",
    response_model=list[DictionaryFieldRead],
)
def list_dictionary_fields(
    project_id: uuid.UUID = Query(...),
    search: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    normalized_data_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    require_project_access(
        db,
        user_id=session.user.id,
        project_id=project_id,
    )

    statement = (
        select(
            DataField.id.label("field_id"),
            DataField.field_name,
            DataField.ordinal_position,
            DataField.native_data_type,
            DataField.normalized_data_type,
            DataField.is_nullable,
            DataField.is_primary_key,
            DataField.is_unique,
            SourceObject.id.label("source_object_id"),
            SourceObject.object_name,
            SourceObject.object_type,
            DataSource.id.label("data_source_id"),
            DataSource.name.label("data_source_name"),
            DataSource.source_type,
        )
        .join(
            SourceObject,
            DataField.source_object_id == SourceObject.id,
        )
        .join(
            DataSource,
            SourceObject.data_source_id == DataSource.id,
        )
        .where(
            DataSource.project_id == project_id
        )
    )

    if search:
        statement = statement.where(
            DataField.field_name.ilike(
                f"%{search.strip()}%"
            )
        )

    if source_type:
        statement = statement.where(
            DataSource.source_type == source_type
        )

    if normalized_data_type:
        statement = statement.where(
            DataField.normalized_data_type
            == normalized_data_type
        )

    statement = statement.order_by(
        DataSource.name,
        SourceObject.object_name,
        DataField.ordinal_position,
    )

    rows = db.execute(statement).mappings().all()

    return [
        DictionaryFieldRead(**row)
        for row in rows
    ]