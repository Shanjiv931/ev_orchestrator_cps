from app.config import settings
from app.models import User
from app.seed import seed_admin_if_missing


def test_seed_admin_if_missing_creates_exactly_one_admin(db_session):
    assert db_session.query(User).filter(User.persona == "city_admin").count() == 0
    seed_admin_if_missing(db_session)
    admins = db_session.query(User).filter(User.persona == "city_admin").all()
    assert len(admins) == 1
    assert admins[0].email == settings.admin_seed_email


def test_seed_admin_if_missing_is_idempotent(db_session):
    seed_admin_if_missing(db_session)
    seed_admin_if_missing(db_session)
    assert db_session.query(User).filter(User.persona == "city_admin").count() == 1


def _make_admin_headers(client, db_session, email: str) -> dict:
    reg = client.post("/auth/register", json={
        "name": "Admin", "email": email, "password": "adminpass123", "persona": "individual_driver",
    })
    token = reg.json()["access_token"]
    user = db_session.query(User).filter(User.email == email).first()
    user.persona = "city_admin"
    db_session.commit()
    return {"Authorization": f"Bearer {token}"}


def test_cannot_register_as_city_admin_directly(client):
    response = client.post("/auth/register", json={
        "name": "X", "email": "wannabe-admin@example.com", "password": "pass1234", "persona": "city_admin",
    })
    assert response.status_code == 403


def test_request_admin_access_and_approval_flow(client, auth_headers, db_session):
    normal_headers = auth_headers("wants-admin@example.com")
    admin_headers = _make_admin_headers(client, db_session, "admin1@example.com")

    req = client.post("/admin/requests", headers=normal_headers)
    assert req.status_code == 201
    request_id = req.json()["id"]

    pending = client.get("/admin/requests", headers=admin_headers)
    assert pending.status_code == 200
    assert any(r["id"] == request_id for r in pending.json())

    approve = client.post(f"/admin/requests/{request_id}/approve", headers=admin_headers)
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    me = client.get("/auth/me", headers=normal_headers)
    assert me.json()["persona"] == "city_admin"


def test_non_admin_cannot_list_requests(client, auth_headers):
    headers = auth_headers("regular-user@example.com")
    response = client.get("/admin/requests", headers=headers)
    assert response.status_code == 403


def test_duplicate_pending_request_rejected(client, auth_headers):
    headers = auth_headers("dup-request@example.com")
    client.post("/admin/requests", headers=headers)
    second = client.post("/admin/requests", headers=headers)
    assert second.status_code == 409


def test_reject_admin_request(client, auth_headers, db_session):
    normal_headers = auth_headers("gets-rejected@example.com")
    admin_headers = _make_admin_headers(client, db_session, "admin3@example.com")

    request_id = client.post("/admin/requests", headers=normal_headers).json()["id"]
    rejected = client.post(f"/admin/requests/{request_id}/reject", headers=admin_headers)
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    me = client.get("/auth/me", headers=normal_headers)
    assert me.json()["persona"] != "city_admin"


def test_admin_users_list_requires_admin(client, auth_headers, db_session):
    admin_headers = _make_admin_headers(client, db_session, "admin2@example.com")
    normal_headers = auth_headers("list-test-user@example.com")

    forbidden = client.get("/admin/users", headers=normal_headers)
    assert forbidden.status_code == 403

    allowed = client.get("/admin/users", headers=admin_headers)
    assert allowed.status_code == 200
    assert any(u["email"] == "list-test-user@example.com" for u in allowed.json())
