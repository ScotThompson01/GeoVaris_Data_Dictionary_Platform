"""GeoVaris FastAPI application and route registration."""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies.auth import require_authenticated_session
from app.api.routes import (
    auth,
    clients,
    data_fields,
    data_sources,
    dictionary,
    discovery,
    field_governance,
    health,
    profiling_results,
    projects,
    scans,
    source_objects,
    user_management,
)
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="GeoVaris Data Dictionary & Data Quality Platform API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Public endpoints.
app.include_router(
    health.router,
    prefix="/api/v1",
    tags=["Health"],
)

app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["Authentication"],
)

# Protected data endpoints.
protected_dependencies = [Depends(require_authenticated_session)]

app.include_router(
    clients.router,
    prefix="/api/v1/clients",
    tags=["Clients"],
    dependencies=protected_dependencies,
)

app.include_router(
    projects.router,
    prefix="/api/v1/projects",
    tags=["Projects"],
    dependencies=protected_dependencies,
)

app.include_router(
    data_sources.router,
    prefix="/api/v1/data-sources",
    tags=["Data Sources"],
    dependencies=protected_dependencies,
)

app.include_router(
    scans.router,
    prefix="/api/v1/scans",
    tags=["Scans"],
    dependencies=protected_dependencies,
)

app.include_router(
    source_objects.router,
    prefix="/api/v1/source-objects",
    tags=["Source Objects"],
    dependencies=protected_dependencies,
)

app.include_router(
    data_fields.router,
    prefix="/api/v1/data-fields",
    tags=["Data Fields"],
    dependencies=protected_dependencies,
)

app.include_router(
    discovery.router,
    prefix="/api/v1/discovery",
    tags=["Discovery"],
    dependencies=protected_dependencies,
)

app.include_router(
    profiling_results.router,
    prefix="/api/v1/profiling-results",
    tags=["Profiling Results"],
    dependencies=protected_dependencies,
)

app.include_router(
    dictionary.router,
    prefix="/api/v1/dictionary",
    tags=["Data Dictionary"],
    dependencies=protected_dependencies,
)

app.include_router(
    field_governance.router,
    prefix="/api/v1/field-governance",
    tags=["Field Governance"],
    dependencies=protected_dependencies,
)

# Installation administrator endpoints.
app.include_router(
    user_management.router,
    prefix="/api/v1/user-management",
    tags=["User Management"],
)

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import request_validation_exception_handler
from starlette.requests import Request


@app.exception_handler(RequestValidationError)
async def safe_user_management_validation_error(
    request: Request,
    exc: RequestValidationError,
):
    if (
        request.method == "POST"
        and request.url.path == "/api/v1/user-management"
    ):
        safe_errors = [
            {
                key: value
                for key, value in error.items()
                if key not in {"input", "ctx", "url"}
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"detail": safe_errors},
            headers={"Cache-Control": "no-store"},
        )

    return await request_validation_exception_handler(request, exc)
