import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import (
    advanced_features,
    auth,
    battery_health,
    carbon_ledger,
    feeders,
    payments,
    sessions,
    stations,
    twin,
    vehicles,
)
from app.services import twin_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    relay_task = asyncio.create_task(twin_client.relay_forever(settings.twin_engine_ws_url))
    yield
    relay_task.cancel()


app = FastAPI(title="EV Charging Orchestrator API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(vehicles.router)
app.include_router(stations.router)
app.include_router(feeders.router)
app.include_router(sessions.router)
app.include_router(battery_health.router)
app.include_router(carbon_ledger.router)
app.include_router(payments.router)
app.include_router(advanced_features.router)
app.include_router(twin.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
