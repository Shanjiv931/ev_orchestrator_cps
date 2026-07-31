import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import (
    admin,
    advanced_features,
    auth,
    battery_health,
    carbon_ledger,
    catalog,
    feeders,
    home_charging,
    oauth,
    payments,
    poi,
    sessions,
    stations,
    twin,
    vehicle_link,
    vehicles,
)
from app.migrate import run_lightweight_migrations
from app.seed import seed_admin_if_missing
from app.seed_provisioning import seed_provisioning_if_empty
from app.seed_stations import seed_stations_if_empty
from app.services import twin_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_lightweight_migrations(engine)
    with SessionLocal() as db:
        seed_admin_if_missing(db)
        seed_stations_if_empty(db)
        seed_provisioning_if_empty(db)
    relay_task = asyncio.create_task(twin_client.relay_forever(settings.twin_engine_ws_url))
    yield
    relay_task.cancel()


app = FastAPI(title="MeridianGrid API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(oauth.router)
app.include_router(admin.router)
app.include_router(catalog.router)
app.include_router(vehicles.router)
app.include_router(vehicle_link.router)
app.include_router(stations.router)
app.include_router(feeders.router)
app.include_router(home_charging.router)
app.include_router(sessions.router)
app.include_router(battery_health.router)
app.include_router(carbon_ledger.router)
app.include_router(payments.router)
app.include_router(poi.router)
app.include_router(advanced_features.router)
app.include_router(twin.router)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
