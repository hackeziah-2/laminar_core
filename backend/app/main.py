
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import (
    flights as flights_router,
    aircraft as aircraft_router,
    auth as auth_router,
)
from app.database import engine, Base
app = FastAPI(title="Laminar API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(flights_router.router)
app.include_router(auth_router.router)
app.include_router(aircraft_router.router)
@app.on_event("startup")
async def startup():
    # create tables in dev mode
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print("Database connection failed:", e)

