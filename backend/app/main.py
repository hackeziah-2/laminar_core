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
    document_on_board as document_on_board_router
)
from app.database import engine, Base

app = FastAPI(title="Laminar API")
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(flights_router.router)
app.include_router(auth_router.router)
app.include_router(aircraft_router.router)
app.include_router(atl_router.router)
app.include_router(atl_new_router.router)
app.include_router(account_router.router)
app.include_router(logbooks_router.router)
app.include_router(document_on_board_router.router)
app.include_router(document_on_board_router.router_aircraft_scoped)

# Shared upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


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

