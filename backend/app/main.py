import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import text
from app.api.v1 import (
    flights as flights_router,
    aircraft as aircraft_router,
    auth as auth_router,
    aircraft_technical_logbook as atl_router,
    aircraft_technical_log as atl_new_router,
    account as account_router,
    logbooks as logbooks_router,
    document_on_board as document_on_board_router,
    ldnd_monitoring as ldnd_monitoring_router,
    ad_monitoring as ad_monitoring_router,
)
from app.database import engine, Base

OPENAPI_TAGS = [
    {"name": "ad-monitoring", "description": "**Aircraft-scoped AD monitoring** – `api/v1/aircraft/{aircraft_fk}/ad_monitoring/` (CRUD). **Work-order AD monitoring** – `api/v1/aircraft/{aircraft_fk}/ad_monitoring/{ad_monitoring_fk}/work-order-ad-monitoring/` (CRUD). See README **AD Monitoring** section."},
    {"name": "work-order-ad-monitoring", "description": "Work-order AD monitoring (global and aircraft-scoped). Global: `api/v1/work-order-ad-monitoring/`. Aircraft-scoped: `api/v1/aircraft/{aircraft_fk}/ad_monitoring/{ad_monitoring_fk}/work-order-ad-monitoring/` (CRUD). See README **AD Monitoring** section."},
]
app = FastAPI(title="Laminar API", openapi_tags=OPENAPI_TAGS)

# CORS: allow localhost (dev) and deployment frontend; override via ALLOWED_ORIGINS env (comma-separated)
_default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://120.89.33.51:3000",   # Deployment frontend
    "http://120.89.33.51:8000",   # Backend (e.g. for docs from same host)
]
_env_origins = os.getenv("ALLOWED_ORIGINS", "").strip()
origins = [o.strip() for o in _env_origins.split(",") if o.strip()] if _env_origins else _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/", tags=["health"])
async def api_v1_root():
    """Health/connectivity check for API v1. Use this to verify backend is running and CORS allows the request."""
    return {"status": "ok", "version": "v1", "message": "Laminar API v1"}


# Shared upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Register download route BEFORE module routers so /api/v1/{module}/download/{filename}
# is matched here instead of being claimed by a module router (e.g. /api/v1/logbooks) and returning 404.
@app.get(
    "/api/v1/{module_folder}/download/{filename:path}",
    summary="Download uploaded file",
    description="Download a file that was uploaded to any module by filename. "
                "Accepts either just the filename or the full path (e.g., 'uploads/filename.pdf'). "
                "The module_folder parameter is for organization but doesn't affect file lookup.",
    response_description="File download",
    tags=["files"]
)
async def download_file(module_folder: str, filename: str):
    """Download an uploaded file from the uploads directory.

    Args:
        module_folder: The module name (e.g., 'logbooks', 'aircraft') - used for organization
        filename: The filename or path to the file (e.g., 'myfile.pdf' or 'uploads/myfile.pdf')
    """
    # Handle both cases: just filename or full path (e.g., "uploads/filename.pdf")
    if filename.startswith("uploads/") or filename.startswith("uploads\\"):
        file_path = Path(filename)
    else:
        file_path = UPLOAD_DIR / filename

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream"
    )


app.include_router(flights_router.router)
app.include_router(auth_router.router)
# Aircraft-scoped sub-routes first (longer paths) so /api/v1/aircraft/{id}/.../ is matched correctly
app.include_router(document_on_board_router.router_aircraft_scoped)
app.include_router(ldnd_monitoring_router.router_aircraft_scoped)
app.include_router(ad_monitoring_router.router_aircraft_scoped)
app.include_router(aircraft_router.router)
app.include_router(atl_router.router)
app.include_router(atl_new_router.router)
app.include_router(account_router.router)
app.include_router(logbooks_router.router)
app.include_router(document_on_board_router.router)
app.include_router(ldnd_monitoring_router.router)
app.include_router(ad_monitoring_router.router)
app.include_router(ad_monitoring_router.router_work_order)

@app.on_event("startup")
async def startup():
    """Startup event - verify database connection.
    
    Note: Tables should be created via Alembic migrations, not create_all().
    This function only tests the connection.
    """
    try:
        # Test database connection
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        print(f"Database connection warning: {e}")
        # Don't fail startup - migrations should handle table creation

