
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import (
    flights as flights_router,
    aircraft as aircraft_router,
    auth as auth_router,
    aircraft_technical_logbook as atl_router
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

@app.on_event("startup")
async def startup():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print("Database connection failed:", e)

