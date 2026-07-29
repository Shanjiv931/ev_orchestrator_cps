import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import Base, engine
from app.routers import auth, battery_health, carbon_ledger, feeders, sessions, stations, twin, vehicles
from app.services import twin_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    relay_task = asyncio.create_task(twin_client.relay_forever(settings.twin_engine_ws_url))
    yield
    relay_task.cancel()


app = FastAPI(title="EV Charging Orchestrator API", version="0.1.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(vehicles.router)
app.include_router(stations.router)
app.include_router(feeders.router)
app.include_router(sessions.router)
app.include_router(battery_health.router)
app.include_router(carbon_ledger.router)
app.include_router(twin.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
