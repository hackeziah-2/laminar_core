
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.api.v1 import (
    flights as flights_router,
    aircraft as aircraft_router,
    auth as auth_router,
    aircraft_technical_logbook as atl_router,
    aircraft_technical_log as atl_new_router
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

