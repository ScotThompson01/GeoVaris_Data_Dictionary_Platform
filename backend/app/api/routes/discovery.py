from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.discovery import CSVDiscoveryRequest
from app.schemas.scan import ScanRead
from app.services.csv_discovery import discover_csv

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