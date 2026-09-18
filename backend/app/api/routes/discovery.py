from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.connectors.database.base import (
    DatabaseConnectionConfig,
)
from app.db.session import get_db
from app.schemas.discovery import (
    CSVDiscoveryRequest,
    PostgreSQLDiscoveryRequest,
    SQLServerDiscoveryRequest,
)
from app.schemas.scan import ScanRead
from app.services.csv_discovery import discover_csv
from app.services.postgresql_discovery import (
    discover_postgresql,
)
from app.services.sqlserver_discovery import (
    discover_sqlserver,
)

router = APIRouter()

SAMPLE_DATA_ROOT = Path("/data/samples")


@router.post(
    "/csv",
    response_model=ScanRead,
    status_code=status.HTTP_201_CREATED,
)
def run_csv_discovery(
    payload: CSVDiscoveryRequest,
    db: Session = Depends(get_db),
):
    requested_name = Path(payload.file_name)

    if requested_name.name != payload.file_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_name must contain only a file name.",
        )

    if requested_name.suffix.lower() != ".csv":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV discovery requires a .csv file.",
        )

    file_path = SAMPLE_DATA_ROOT / requested_name.name

    try:
        return discover_csv(
            db=db,
            data_source_id=payload.data_source_id,
            file_path=file_path,
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CSV file not found.",
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CSV discovery failed.",
        )


@router.post(
    "/postgresql",
    response_model=ScanRead,
    status_code=status.HTTP_201_CREATED,
)
def run_postgresql_discovery(
    payload: PostgreSQLDiscoveryRequest,
    db: Session = Depends(get_db),
):
    """
    Run read-only PostgreSQL metadata discovery.

    Connection credentials are runtime-only and are not persisted
    by the discovery service.
    """

    connection_config = DatabaseConnectionConfig(
        host=payload.host,
        port=payload.port,
        database=payload.database,
        username=payload.username,
        ssl_mode=payload.ssl_mode,
        connect_timeout_seconds=(
            payload.connect_timeout_seconds
        ),
    )

    password = (
        payload.password.get_secret_value()
        if payload.password is not None
        else None
    )

    try:
        return discover_postgresql(
            db=db,
            data_source_id=payload.data_source_id,
            connection_config=connection_config,
            password=password,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    except ConnectionError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unable to connect to or discover metadata "
                "from the PostgreSQL source."
            ),
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PostgreSQL discovery failed.",
        )


@router.post(
    "/sqlserver",
    response_model=ScanRead,
    status_code=status.HTTP_201_CREATED,
)
def run_sqlserver_discovery(
    payload: SQLServerDiscoveryRequest,
    db: Session = Depends(get_db),
):
    """
    Run read-only SQL Server metadata discovery.

    Connection credentials are runtime-only and are not persisted
    by the discovery service.
    """

    connection_config = DatabaseConnectionConfig(
        host=payload.host,
        port=payload.port,
        database=payload.database,
        username=payload.username,
        ssl_mode=payload.ssl_mode,
        connect_timeout_seconds=(
            payload.connect_timeout_seconds
        ),
    )

    password = (
        payload.password.get_secret_value()
        if payload.password is not None
        else None
    )

    try:
        return discover_sqlserver(
            db=db,
            data_source_id=payload.data_source_id,
            connection_config=connection_config,
            password=password,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    except ConnectionError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unable to connect to or discover metadata "
                "from the SQL Server source."
            ),
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SQL Server discovery failed.",
        )