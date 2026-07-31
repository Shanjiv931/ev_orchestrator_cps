import os
import sys
from pathlib import Path

# backend/tests has no __init__.py, so pytest's default import mode inserts
# backend/tests (not backend/) onto sys.path - `app`/`ml` are only
# importable here because `python -m pytest` happens to add the cwd too.
# CI invokes the bare `pytest` command, which does not get that implicit
# insertion, so this must be explicit (same pattern already used in the
# simulation/ and twin-engine/ test suites).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Tests truncate tables between cases and drop the whole schema at session
# end (see _schema below) - running that against whatever database the app
# itself is already pointed at would wipe real data. `docker compose exec
# backend` inherits POSTGRES_DSN from docker-compose.yml (the real
# ev_orchestrator database), so `setdefault` here was a no-op and every test
# run was silently dropping the live dev database's schema. Force a
# "_test"-suffixed database name unconditionally instead, keeping whatever
# host/user/password is already configured for this environment.
_default_dsn = "postgresql+psycopg2://ev:ev@localhost:5432/ev_orchestrator_test"
_base_dsn = os.environ.get("POSTGRES_DSN", _default_dsn)
_dsn_base, _, _db_name = _base_dsn.rpartition("/")
os.environ["POSTGRES_DSN"] = _base_dsn if _db_name.endswith("_test") else f"{_dsn_base}/{_db_name}_test"
os.environ.setdefault("TWIN_ENGINE_WS_URL", "ws://127.0.0.1:1/ws")  # deliberately unreachable in tests

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.auth import create_access_token, hash_password
from app.database import Base, get_db
from app.main import app
from app.models import User, Vehicle

engine = create_engine(os.environ["POSTGRES_DSN"])
TestingSessionLocal = sessionmaker(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    """A real session doing real commits, matching how the app itself uses
    the database - each test starts from a clean slate via TRUNCATE rather
    than a rolled-back transaction, since the endpoints under test perform
    their own commits/rollbacks and a held-open outer transaction fights
    with that."""
    session = TestingSessionLocal()
    yield session
    session.close()
    table_names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {table_names} CASCADE"))


@pytest.fixture(scope="session")
def _test_client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def client(_test_client, db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    yield _test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def auth_headers(db_session):
    def _register(email: str, persona: str = "individual_driver") -> dict:
        # POST /auth/register no longer persists a User row or returns a
        # token at all - it only creates a pending (Redis-backed)
        # registration, and the real account only exists once its OTP is
        # verified (see app/routers/auth.py). Tests care about exercising
        # the feature under test with a working authenticated user, not
        # re-deriving that OTP dance every time, so this constructs the
        # verified account directly, the same way test_admin_workflow.py's
        # _make_admin_headers does.
        user = User(
            name="Test User", email=email, hashed_password=hash_password("correct-horse-battery-staple"),
            persona=persona, dpdp_consent_flag=True, email_verified=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        token = create_access_token(user.id, user.persona)
        return {"Authorization": f"Bearer {token}"}

    return _register


@pytest.fixture()
def create_test_vehicle(db_session):
    """Vehicles now only come into existence via the admin-approved
    request flow (see app/routers/vehicles.py / admin.py) - tests that are
    exercising something else (sessions, payments, battery health, pairing)
    just need *a* vehicle to exist for a user, the same way auth_headers
    above bypasses the OTP dance to get a working authenticated user."""
    def _create(owner_email: str, vehicle_class: str = "4W", connector_type: str = "CCS2",
                battery_chemistry: str = "NMC", is_pluggable: bool = True,
                battery_capacity_kwh: float = 40.0, number_plate: str = "TN23AB1234") -> Vehicle:
        owner = db_session.query(User).filter(User.email == owner_email).first()
        vehicle = Vehicle(
            user_id=owner.id, vehicle_class=vehicle_class, connector_type=connector_type,
            battery_chemistry=battery_chemistry, is_pluggable=is_pluggable,
            battery_capacity_kwh=battery_capacity_kwh, number_plate=number_plate,
        )
        db_session.add(vehicle)
        db_session.commit()
        db_session.refresh(vehicle)
        return vehicle

    return _create
