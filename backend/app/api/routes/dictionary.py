import csv
import io
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.api.dependencies.auth import (
    AuthenticatedSession,
    require_authenticated_session,
)
from app.db.session import get_db
from app.models.data_field import DataField
from app.models.data_source import DataSource
from app.models.field_governance_metadata import FieldGovernanceMetadata
from app.models.source_object import SourceObject
from app.schemas.dictionary import DictionaryFieldRead
from app.services.project_authorization import require_project_access

router = APIRouter()


def _safe_spreadsheet_value(value: object) -> object:
    """Prevent text values from being interpreted as spreadsheet formulas."""
    if not isinstance(value, str):
        return value

    stripped = value.lstrip()
    if stripped.startswith(("=", "+", "-", "@")):
        value = "'" + value

    return value[:32767]


def _apply_dictionary_filters(
    statement: Select,
    *,
    project_id: uuid.UUID,
    search: str | None,
    source_type: str | None,
    data_source_id: uuid.UUID | None,
    department: str | None,
    data_owner: str | None,
    is_cde: bool | None,
    normalized_data_type: str | None,
) -> Select:
    """Apply the shared project scope and dictionary filters."""
    statement = statement.where(DataSource.project_id == project_id)

    if search:
        statement = statement.where(
            DataField.field_name.ilike(f"%{search.strip()}%")
        )

    if source_type:
        statement = statement.where(DataSource.source_type == source_type)

    if data_source_id is not None:
        statement = statement.where(DataSource.id == data_source_id)

    if department:
        statement = statement.where(
            FieldGovernanceMetadata.department == department
        )

    if data_owner:
        statement = statement.where(
            FieldGovernanceMetadata.data_owner == data_owner
        )

    if is_cde is not None:
        statement = statement.where(
            func.coalesce(FieldGovernanceMetadata.is_cde, False) == is_cde
        )

    if normalized_data_type:
        statement = statement.where(
            DataField.normalized_data_type == normalized_data_type
        )

    return statement.order_by(
        DataSource.name,
        SourceObject.object_name,
        DataField.ordinal_position,
    )


def _build_dictionary_export_statement() -> Select:
    """Build the metadata-only query used by dictionary exports."""
    return (
        select(
            DataSource.name.label("data_source_name"),
            DataSource.source_type,
            SourceObject.schema_name,
            SourceObject.object_name,
            SourceObject.object_type,
            SourceObject.native_name,
            SourceObject.description.label("object_description"),
            SourceObject.row_count.label("object_row_count"),
            DataField.field_name,
            DataField.ordinal_position,
            DataField.native_data_type,
            DataField.normalized_data_type,
            DataField.max_length,
            DataField.numeric_precision,
            DataField.numeric_scale,
            DataField.is_nullable,
            DataField.is_primary_key,
            DataField.is_unique,
            DataField.default_value,
            DataField.source_comment,
            FieldGovernanceMetadata.business_name,
            FieldGovernanceMetadata.business_definition,
            FieldGovernanceMetadata.department,
            FieldGovernanceMetadata.data_owner,
            FieldGovernanceMetadata.data_steward,
            FieldGovernanceMetadata.business_process,
            FieldGovernanceMetadata.system_of_record,
            func.coalesce(
                FieldGovernanceMetadata.is_cde,
                False,
            ).label("is_cde"),
            FieldGovernanceMetadata.classification,
            func.coalesce(
                FieldGovernanceMetadata.approval_status,
                "draft",
            ).label("approval_status"),
            FieldGovernanceMetadata.notes,
        )
        .join(
            SourceObject,
            DataField.source_object_id == SourceObject.id,
        )
        .join(
            DataSource,
            SourceObject.data_source_id == DataSource.id,
        )
        .outerjoin(
            FieldGovernanceMetadata,
            FieldGovernanceMetadata.data_field_id == DataField.id,
        )
    )


def _build_csv_export(rows: list[dict]) -> bytes:
    """Serialize dictionary metadata rows as UTF-8 CSV."""
    output = io.StringIO(newline="")
    writer = csv.writer(output)

    writer.writerow(
        header
        for _, header in DICTIONARY_EXPORT_COLUMNS
    )

    for row in rows:
        writer.writerow(
            _safe_spreadsheet_value(row.get(key))
            for key, _ in DICTIONARY_EXPORT_COLUMNS
        )

    return output.getvalue().encode("utf-8-sig")


def _build_xlsx_export(rows: list[dict]) -> bytes:
    """Serialize dictionary metadata rows as an in-memory XLSX workbook."""
    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet(title="Data Dictionary")

    worksheet.append(
        [header for _, header in DICTIONARY_EXPORT_COLUMNS]
    )

    for row in rows:
        worksheet.append(
            [
                _safe_spreadsheet_value(row.get(key))
                for key, _ in DICTIONARY_EXPORT_COLUMNS
            ]
        )

    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


DICTIONARY_EXPORT_COLUMNS = (
    ("data_source_name", "Data Source"),
    ("source_type", "Source Type"),
    ("schema_name", "Schema"),
    ("object_name", "Object"),
    ("object_type", "Object Type"),
    ("native_name", "Native Object Name"),
    ("object_description", "Object Description"),
    ("object_row_count", "Object Row Count"),
    ("field_name", "Field Name"),
    ("ordinal_position", "Ordinal Position"),
    ("native_data_type", "Native Data Type"),
    ("normalized_data_type", "Normalized Data Type"),
    ("max_length", "Max Length"),
    ("numeric_precision", "Numeric Precision"),
    ("numeric_scale", "Numeric Scale"),
    ("is_nullable", "Nullable"),
    ("is_primary_key", "Primary Key"),
    ("is_unique", "Unique"),
    ("default_value", "Default Value"),
    ("source_comment", "Source Comment"),
    ("business_name", "Business Name"),
    ("business_definition", "Business Definition"),
    ("department", "Department"),
    ("data_owner", "Data Owner"),
    ("data_steward", "Data Steward"),
    ("business_process", "Business Process"),
    ("system_of_record", "System of Record"),
    ("is_cde", "Critical Data Element"),
    ("classification", "Classification"),
    ("approval_status", "Approval Status"),
    ("notes", "Notes"),
)


@router.get(
    "",
    response_model=list[DictionaryFieldRead],
)
def list_dictionary_fields(
    project_id: uuid.UUID = Query(...),
    search: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    data_source_id: uuid.UUID | None = Query(default=None),
    department: str | None = Query(default=None),
    data_owner: str | None = Query(default=None),
    is_cde: bool | None = Query(default=None),
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
            DataField.max_length,
            DataField.numeric_precision,
            DataField.numeric_scale,
            DataField.default_value,
            DataField.source_comment,
            DataField.is_nullable,
            DataField.is_primary_key,
            DataField.is_unique,
            SourceObject.id.label("source_object_id"),
            SourceObject.object_name,
            SourceObject.object_type,
            SourceObject.schema_name,
            SourceObject.native_name,
            SourceObject.description.label("object_description"),
            SourceObject.row_count.label("object_row_count"),
            DataSource.id.label("data_source_id"),
            DataSource.name.label("data_source_name"),
            DataSource.source_type,
            FieldGovernanceMetadata.department,
            FieldGovernanceMetadata.data_owner,
            func.coalesce(FieldGovernanceMetadata.is_cde, False).label("is_cde"),
        )
        .join(
            SourceObject,
            DataField.source_object_id == SourceObject.id,
        )
        .join(
            DataSource,
            SourceObject.data_source_id == DataSource.id,
        )
        .outerjoin(
            FieldGovernanceMetadata,
            FieldGovernanceMetadata.data_field_id == DataField.id,
        )
    )

    statement = _apply_dictionary_filters(
        statement,
        project_id=project_id,
        search=search,
        source_type=source_type,
        data_source_id=data_source_id,
        department=department,
        data_owner=data_owner,
        is_cde=is_cde,
        normalized_data_type=normalized_data_type,
    )
    rows = db.execute(statement).mappings().all()

    return [
        DictionaryFieldRead(**row)
        for row in rows
    ]

@router.get("/export")
def export_dictionary(
    project_id: uuid.UUID = Query(...),
    format: Literal["csv", "xlsx"] = Query(...),
    search: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    data_source_id: uuid.UUID | None = Query(default=None),
    department: str | None = Query(default=None),
    data_owner: str | None = Query(default=None),
    is_cde: bool | None = Query(default=None),
    normalized_data_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(require_authenticated_session),
):
    """Export authorized dictionary metadata as CSV or XLSX."""
    require_project_access(
        db,
        user_id=session.user.id,
        project_id=project_id,
    )

    statement = _apply_dictionary_filters(
        _build_dictionary_export_statement(),
        project_id=project_id,
        search=search,
        source_type=source_type,
        data_source_id=data_source_id,
        department=department,
        data_owner=data_owner,
        is_cde=is_cde,
        normalized_data_type=normalized_data_type,
    )

    rows = [
        dict(row)
        for row in db.execute(statement).mappings().all()
    ]

    if format == "csv":
        content = _build_csv_export(rows)
        media_type = "text/csv; charset=utf-8"
        filename = f"geovaris-data-dictionary-{project_id}.csv"
    else:
        content = _build_xlsx_export(rows)
        media_type = (
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
        filename = f"geovaris-data-dictionary-{project_id}.xlsx"

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
