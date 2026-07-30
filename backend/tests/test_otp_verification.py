from datetime import datetime, timedelta, timezone

from app.models import User
from app.routers.oauth import _find_or_create_oauth_user


def _register(client, email: str) -> tuple[dict, str]:
    response = client.post("/auth/register", json={
        "name": "Otp Test", "email": email, "password": "correct-horse-battery-staple", "persona": "individual_driver",
    })
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, email


def test_unverified_account_is_blocked_from_protected_endpoints(client, db_session):
    headers, email = _register(client, "unverified@example.com")
    response = client.get("/vehicles", headers=headers)
    assert response.status_code == 403
    assert "not verified" in response.json()["detail"]


def test_me_works_even_when_unverified(client):
    headers, email = _register(client, "stillunverified@example.com")
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email_verified"] is False


def test_wrong_otp_code_is_rejected(client):
    headers, _ = _register(client, "wrongcode@example.com")
    response = client.post("/auth/verify-otp", json={"otp_code": "000000"}, headers=headers)
    assert response.status_code == 400


def test_correct_otp_code_verifies_and_unblocks(client, db_session, monkeypatch):
    captured = {}
    monkeypatch.setattr("app.routers.auth.send_otp_email", lambda to, code: captured.update(code=code))

    headers, email = _register(client, "correctcode@example.com")
    assert "code" in captured

    response = client.post("/auth/verify-otp", json={"otp_code": captured["code"]}, headers=headers)
    assert response.status_code == 200
    assert response.json()["email_verified"] is True

    response = client.get("/vehicles", headers=headers)
    assert response.status_code == 200


def test_resend_otp_issues_a_new_working_code(client, db_session, monkeypatch):
    codes = []
    monkeypatch.setattr("app.routers.auth.send_otp_email", lambda to, code: codes.append(code))

    headers, email = _register(client, "resend@example.com")
    first_code = codes[0]

    # bypass the resend cooldown for this test by rewinding otp_expires_at
    db_session.query(User).filter(User.email == email).update(
        {"otp_expires_at": datetime.now(timezone.utc) - timedelta(hours=1)}
    )
    db_session.commit()

    response = client.post("/auth/resend-otp", headers=headers)
    assert response.status_code == 204
    second_code = codes[1]
    assert second_code != first_code

    # the old code no longer works, the new one does
    assert client.post("/auth/verify-otp", json={"otp_code": first_code}, headers=headers).status_code == 400
    assert client.post("/auth/verify-otp", json={"otp_code": second_code}, headers=headers).status_code == 200


def test_resend_otp_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr("app.routers.auth.send_otp_email", lambda to, code: None)
    headers, _ = _register(client, "cooldown@example.com")
    response = client.post("/auth/resend-otp", headers=headers)
    assert response.status_code == 429


def test_new_google_account_starts_verified(db_session):
    user = _find_or_create_oauth_user(
        db_session, oauth_subject="google-sub-123", email="googleuser@example.com", name="Google User", provider="google",
    )
    assert user.email_verified is True


def test_linking_google_to_existing_password_account_verifies_it(client, db_session):
    headers, email = _register(client, "linkme@example.com")
    user = db_session.query(User).filter(User.email == email).first()
    assert user.email_verified is False

    linked = _find_or_create_oauth_user(
        db_session, oauth_subject="google-sub-456", email=email, name="Link Me", provider="google",
    )
    assert linked.email_verified is True
