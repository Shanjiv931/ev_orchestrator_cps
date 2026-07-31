import json
from datetime import datetime, timedelta, timezone

from app.auth import hash_password
from app.models import User
from app.pending_registration import get_pending_registration
from app.redis_client import redis_client
from app.routers.oauth import _find_or_create_oauth_user


_VALID_REGISTRATION_EXTRAS = {
    "date_of_birth": "1995-06-15",
    "phone_number": "+919876543210",
    "license_number": "TN01820230012345",
    "license_expiry": "2030-06-15",
    "profession": "Software Engineer",
}


def _register(client, email: str, monkeypatch) -> tuple[str, list]:
    codes: list[str] = []
    monkeypatch.setattr("app.routers.auth.send_otp_email", lambda to, code: codes.append(code))
    response = client.post("/auth/register", json={
        "name": "Otp Test", "email": email, "password": "correct-horse-battery-staple", "persona": "individual_driver",
        **_VALID_REGISTRATION_EXTRAS,
    })
    assert response.status_code == 201, response.text
    return response.json()["pending_registration_id"], codes


def test_registration_creates_no_user_row_until_verified(client, db_session, monkeypatch):
    pending_id, codes = _register(client, "notyetsaved@example.com", monkeypatch)

    assert db_session.query(User).filter(User.email == "notyetsaved@example.com").first() is None
    assert get_pending_registration(pending_id) is not None

    response = client.post("/auth/verify-otp", json={"pending_registration_id": pending_id, "otp_code": codes[0]})
    assert response.status_code == 200
    assert "access_token" in response.json()

    assert db_session.query(User).filter(User.email == "notyetsaved@example.com").first() is not None
    assert get_pending_registration(pending_id) is None


def test_unverified_registration_cannot_access_protected_endpoints(client, monkeypatch):
    # there's no token at all yet - nothing to even attempt authenticating with
    pending_id, _ = _register(client, "noaccessyet@example.com", monkeypatch)
    response = client.get("/vehicles")
    assert response.status_code == 401


def test_wrong_otp_code_is_rejected(client, monkeypatch):
    pending_id, _ = _register(client, "wrongcode@example.com", monkeypatch)
    response = client.post("/auth/verify-otp", json={"pending_registration_id": pending_id, "otp_code": "000000"})
    assert response.status_code == 400


def test_unknown_pending_registration_id_is_rejected(client):
    response = client.post("/auth/verify-otp", json={"pending_registration_id": "does-not-exist", "otp_code": "123456"})
    assert response.status_code == 400


def test_correct_otp_code_verifies_and_unblocks(client, monkeypatch):
    pending_id, codes = _register(client, "correctcode@example.com", monkeypatch)

    response = client.post("/auth/verify-otp", json={"pending_registration_id": pending_id, "otp_code": codes[0]})
    assert response.status_code == 200
    token = response.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "correctcode@example.com"
    assert me.json()["email_verified"] is True

    assert client.get("/vehicles", headers=headers).status_code == 200


def test_resend_otp_issues_a_new_working_code(client, monkeypatch):
    pending_id, codes = _register(client, "resend@example.com", monkeypatch)
    first_code = codes[0]

    # bypass the resend cooldown for this test by rewinding last_sent_at
    data = get_pending_registration(pending_id)
    data["last_sent_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    redis_client.setex(f"pending_registration:{pending_id}", 3600, json.dumps(data))

    response = client.post("/auth/resend-otp", json={"pending_registration_id": pending_id})
    assert response.status_code == 204
    second_code = codes[1]
    assert second_code != first_code

    assert client.post(
        "/auth/verify-otp", json={"pending_registration_id": pending_id, "otp_code": first_code},
    ).status_code == 400
    assert client.post(
        "/auth/verify-otp", json={"pending_registration_id": pending_id, "otp_code": second_code},
    ).status_code == 200


def test_resend_otp_is_rate_limited(client, monkeypatch):
    pending_id, _ = _register(client, "cooldown@example.com", monkeypatch)
    response = client.post("/auth/resend-otp", json={"pending_registration_id": pending_id})
    assert response.status_code == 429


def test_resend_otp_for_unknown_registration_is_rejected(client):
    response = client.post("/auth/resend-otp", json={"pending_registration_id": "does-not-exist"})
    assert response.status_code == 400


def test_new_google_account_starts_verified(db_session):
    user = _find_or_create_oauth_user(
        db_session, oauth_subject="google-sub-123", email="googleuser@example.com", name="Google User", provider="google",
    )
    assert user.email_verified is True


def test_linking_google_to_existing_password_account_verifies_it(client, db_session):
    user = User(
        name="Link Me", email="linkme@example.com", hashed_password=hash_password("x"),
        persona="individual_driver", dpdp_consent_flag=True, email_verified=False,
    )
    db_session.add(user)
    db_session.commit()

    linked = _find_or_create_oauth_user(
        db_session, oauth_subject="google-sub-456", email="linkme@example.com", name="Link Me", provider="google",
    )
    assert linked.email_verified is True
