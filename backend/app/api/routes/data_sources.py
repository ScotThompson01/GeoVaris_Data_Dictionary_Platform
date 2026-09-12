import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.data_source import DataSource
from app.models.project import Project
from app.schemas.data_source import DataSourceCreate, DataSourceRead

router = APIRouter()


@router.get(
    "",
    response_model=list[DataSourceRead],
)
def list_data_sources(
    project_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    statement = select(DataSource)

    if project_id is not None:
        statement = statement.where(
            DataSource.project_id == project_id
        )

    statement = statement.order_by(
        DataSource.name
    )

    return db.scalars(statement).all()


@router.post(
    "",
    response_model=DataSourceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_data_source(
    payload: DataSourceCreate,
    db: Session = Depends(get_db),
):
    project = db.get(
        Project,
        payload.project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    data_source = DataSource(
        project_id=payload.project_id,
        name=payload.name.strip(),
        source_type=payload.source_type,
        description=payload.description,
        connection_mode=payload.connection_mode,
        is_active=payload.is_active,
    )

    db.add(data_source)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A data source with this name already "
                "exists for the project."
            ),
        )

    db.refresh(data_source)

    return data_source


@router.get(
    "/{data_source_id}",
    response_model=DataSourceRead,
)
def get_data_source(
    data_source_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    data_source = db.get(
        DataSource,
        data_source_id,
    )

    if data_source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found.",
        )

    return data_source