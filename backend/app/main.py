import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi import UploadFile, File
from sqlalchemy import text
from app.api.v1 import (
    flights as flights_router,
    aircraft as aircraft_router,
    data_import as excel_data_router,
    auth as auth_router,
    aircraft_technical_logbook as atl_router,
    aircraft_technical_log as atl_new_router,
    atl as atl_paged_router,
    account as account_router,
    role as role_router,
    module as module_router,
    logbooks as logbooks_router,
    document_on_board as document_on_board_router,
    ldnd_monitoring as ldnd_monitoring_router,
    ad_monitoring as ad_monitoring_router,
    tcc_maintenance as tcc_maintenance_router,
    cpcp_monitoring as cpcp_monitoring_router,
)
from app.database import engine, Base
from app.upload_config import UPLOAD_DIR, ensure_uploads_dir

OPENAPI_TAGS = [
    {"name": "ad-monitoring", "description": "**Aircraft-scoped AD monitoring** – `api/v1/aircraft/{aircraft_fk}/ad_monitoring/` (CRUD). **Work-order AD monitoring** – `api/v1/aircraft/{aircraft_fk}/ad_monitoring/{ad_monitoring_fk}/work-order-ad-monitoring/` (CRUD). See README **AD Monitoring** section."},
    {"name": "work-order-ad-monitoring", "description": "Work-order AD monitoring (global and aircraft-scoped). Global: `api/v1/work-order-ad-monitoring/`. Aircraft-scoped: `api/v1/aircraft/{aircraft_fk}/ad_monitoring/{ad_monitoring_fk}/work-order-ad-monitoring/` (CRUD). See README **AD Monitoring** section."},
]
app = FastAPI(title="Laminar API", openapi_tags=OPENAPI_TAGS)

# CORS: allow localhost (dev) and deployment; override via ALLOWED_ORIGINS env (comma-separated)
_default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://120.89.33.51",
    "http://120.89.33.51:3000",
    "http://120.89.33.51:8000",
]
_env_origins = os.getenv("ALLOWED_ORIGINS", "").strip()
origins = [o.strip() for o in _env_origins.split(",") if o.strip()] if _env_origins else _default_origins

# Allow deployment IP on any port (e.g. frontend on :80 or :3000) and localhost
_origin_regex = r"^https?://(localhost|127\.0\.0\.1|120\.89\.33\.51)(:\d+)?$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.get("/", tags=["health"])
async def root():
    """Root health check for public deployment (e.g. http://120.89.33.51:8000/)."""
    return {"status": "ok", "message": "Laminar API", "docs": "/docs", "api": "/api/v1/"}


@app.get("/api/v1/", tags=["health"])
async def api_v1_root():
    """Health/connectivity check for API v1. Use this to verify backend is running and CORS allows the request."""
    return {"status": "ok", "version": "v1", "message": "Laminar API v1"}


@app.get("/api/v1/health", tags=["health"])
async def api_v1_health():
    """Health check including uploads directory (for deployment debugging)."""
    uploads_ok = UPLOAD_DIR.is_dir()
    try:
        probe = UPLOAD_DIR / ".write_probe"
        probe.touch()
        probe.unlink()
        uploads_writable = True
    except OSError:
        uploads_writable = False
    return {
        "status": "ok",
        "uploads_dir": str(UPLOAD_DIR),
        "uploads_exists": uploads_ok,
        "uploads_writable": uploads_writable,
    }


# Ensure uploads dir exists before any route uses it (absolute path, independent of CWD)
ensure_uploads_dir()


def _is_safe_module(name: str) -> bool:
    """Allow only alphanumeric, underscore, hyphen (no path traversal)."""
    return bool(name) and all(c.isalnum() or c in "_-" for c in name)


def _resolve_and_serve_file(filename: str, module_folder: Optional[str] = None):
    """Normalize filename, resolve path under UPLOAD_DIR, try flat then module subfolder; return FileResponse or raise 404."""
    filename = filename.lstrip("/").replace("\\", "/")
    if filename.startswith("uploads/"):
        filename = filename[8:]
    base_name = filename.split("/")[-1] if "/" in filename else filename
    if not base_name or ".." in base_name or ".." in filename:
        raise HTTPException(status_code=404, detail="File not found")

    def safe_path(*parts: str) -> Path:
        for p in parts:
            if not p or ".." in p or "/" in p or "\\" in p:
                return None
        path = (UPLOAD_DIR / "/".join(parts)).resolve()
        if not str(path).startswith(str(UPLOAD_DIR)) or not path.is_file():
            return None
        return path

    # Try 1: flat path (uploads/ATL.jpg)
    file_path = safe_path(filename)
    # Try 2: module subfolder (uploads/white_atl/ATL.jpg)
    if file_path is None and module_folder and _is_safe_module(module_folder):
        file_path = safe_path(module_folder, base_name)
    if file_path is None:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )


# Download route (path): /api/v1/{module}/download/{filename} – BEFORE module routers
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
    """Download an uploaded file from the uploads directory (filename in path)."""
    return _resolve_and_serve_file(filename, module_folder)


# Download route (query): /api/v1/{module}/download?name=filename – optional "name"
@app.get(
    "/api/v1/{module_folder}/download",
    summary="Download uploaded file (by query param)",
    description="Download a file by query parameter 'name' (filename). Use when the frontend calls .../download?name=filename.",
    response_description="File download",
    tags=["files"],
)
async def download_file_by_name(
    module_folder: str,
    name: Optional[str] = Query(None, description="Filename to download (e.g. ATL.jpg)"),
):
    """Download an uploaded file when filename is passed as query param 'name'."""
    if not name or not name.strip():
        raise HTTPException(
            status_code=422,
            detail="Query parameter 'name' is required (e.g. ?name=ATL.jpg). Alternatively use path: .../download/{filename}",
        )
    return _resolve_and_serve_file(name.strip(), module_folder)


# Generic upload: POST /api/v1/{module_folder}/upload – "name" is optional (avoids "field required" when frontend omits it)
@app.post(
    "/api/v1/{module_folder}/upload",
    summary="Upload a file",
    description="Upload a file. Query param 'name' is optional; when omitted, the uploaded filename is used.",
    response_description="Uploaded file path",
    tags=["files"],
)
async def upload_file(
    module_folder: str,
    file: UploadFile = File(...),
    name: Optional[str] = Query(None, description="Optional filename override; when omitted, use the uploaded file's name"),
):
    """Upload a file to the shared uploads directory. 'name' query param is optional."""
    ensure_uploads_dir()
    save_name = (name.strip() if name and name.strip() else None) or (file.filename or "upload")
    # Sanitize: keep only the base name to avoid path traversal
    save_name = save_name.split("/")[-1].split("\\")[-1] if save_name else "upload"
    if not save_name or ".." in save_name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = UPLOAD_DIR / save_name
    try:
        content = await file.read()
        file_path.write_bytes(content)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    # Return path that works for download (relative to uploads)
    return {"file_path": f"uploads/{save_name}", "filename": save_name}


app.include_router(flights_router.router)
app.include_router(auth_router.router)
# Aircraft-scoped sub-routes first (longer paths) so /api/v1/aircraft/{id}/.../ is matched correctly
app.include_router(document_on_board_router.router_aircraft_scoped)
app.include_router(ldnd_monitoring_router.router_aircraft_scoped)
app.include_router(ad_monitoring_router.router_aircraft_scoped)
app.include_router(tcc_maintenance_router.router_aircraft_scoped)
app.include_router(aircraft_router.router)
app.include_router(atl_router.router)
app.include_router(atl_new_router.router)
app.include_router(atl_paged_router.router)
app.include_router(account_router.router)
app.include_router(role_router.router)
app.include_router(module_router.router)
app.include_router(logbooks_router.router)
app.include_router(document_on_board_router.router)
app.include_router(tcc_maintenance_router.router)
app.include_router(ldnd_monitoring_router.router)
app.include_router(ad_monitoring_router.router)
app.include_router(ad_monitoring_router.router_work_order)
app.include_router(cpcp_monitoring_router.router)
app.include_router(excel_data_router.router)

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

