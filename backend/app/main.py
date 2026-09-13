from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import clients,data_fields, data_sources, dictionary, discovery, health, profiling_results, projects, scans, source_objects
from app.core.config import settings
app=FastAPI(title=settings.app_name,version="0.2.0",description="GeoVaris Data Dictionary & Data Quality Platform API")
app.add_middleware(CORSMiddleware,allow_origins=[settings.frontend_origin],allow_credentials=False,allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],allow_headers=["Content-Type","Authorization"])
app.include_router(health.router,prefix="/api/v1",tags=["Health"])
app.include_router(clients.router,prefix="/api/v1/clients",tags=["Clients"])
app.include_router(projects.router,prefix="/api/v1/projects",tags=["Projects"])
app.include_router(
    data_sources.router,
    prefix="/api/v1/data-sources",
    tags=["Data Sources"],
)
app.include_router(
    scans.router,
    prefix="/api/v1/scans",
    tags=["Scans"],
)

app.include_router(
    source_objects.router,
    prefix="/api/v1/source-objects",
    tags=["Source Objects"],
)

app.include_router(
    data_fields.router,
    prefix="/api/v1/data-fields",
    tags=["Data Fields"],
)

app.include_router(
    discovery.router,
    prefix="/api/v1/discovery",
    tags=["Discovery"],
)

app.include_router(
    profiling_results.router,
    prefix="/api/v1/profiling-results",
    tags=["Profiling Results"],
)

app.include_router(
    dictionary.router,
    prefix="/api/v1/dictionary",
    tags=["Data Dictionary"],
)