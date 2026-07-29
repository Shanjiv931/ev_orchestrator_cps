import os

os.environ["POSTGRES_DSN"] = "postgresql+psycopg2://ev:ev@localhost:5432/ev_orchestrator_test"
os.environ["TWIN_ENGINE_WS_URL"] = "ws://127.0.0.1:1/ws"  # deliberately unreachable in tests

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

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
def auth_headers(client):
    def _register(email: str, persona: str = "individual_driver") -> dict:
        response = client.post("/auth/register", json={
            "name": "Test User",
            "email": email,
            "password": "correct-horse-battery-staple",
            "persona": persona,
        })
        assert response.status_code == 201, response.text
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _register
