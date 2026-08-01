_VALID_REGISTRATION_EXTRAS = {
    "date_of_birth": "1995-06-15",
    "phone_number": "+919876543210",
    "license_number": "TN01820230012345",
    "license_expiry": "2030-06-15",
    "profession": "Software Engineer",
}


def test_register_returns_pending_registration(client):
    response = client.post("/auth/register", json={
        "name": "Asha", "email": "asha@example.com", "password": "hunter2pass", "persona": "individual_driver",
        **_VALID_REGISTRATION_EXTRAS,
    })
    assert response.status_code == 201
    body = response.json()
    assert "pending_registration_id" in body
    assert body["email"] == "asha@example.com"


def test_register_rejects_under_18(client):
    response = client.post("/auth/register", json={
        "name": "Too Young", "email": "tooyoung@example.com", "password": "hunter2pass", "persona": "individual_driver",
        **{**_VALID_REGISTRATION_EXTRAS, "date_of_birth": "2015-01-01"},
    })
    assert response.status_code == 422


def test_registering_same_unverified_email_twice_is_allowed(client):
    # No row is persisted until OTP verification (see app/routers/auth.py),
    # so there's no real account yet for a second attempt to conflict with -
    # each gets its own independent pending registration.
    payload = {
        "name": "Asha", "email": "dup@example.com", "password": "hunter2pass", "persona": "individual_driver",
        **_VALID_REGISTRATION_EXTRAS,
    }
    first = client.post("/auth/register", json=payload)
    second = client.post("/auth/register", json=payload)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["pending_registration_id"] != second.json()["pending_registration_id"]


def test_registering_an_already_verified_email_conflicts(client, auth_headers):
    auth_headers("already-verified@example.com")
    response = client.post("/auth/register", json={
        "name": "X", "email": "already-verified@example.com", "password": "hunter2pass", "persona": "individual_driver",
        **_VALID_REGISTRATION_EXTRAS,
    })
    assert response.status_code == 409


def test_login_with_correct_password_succeeds(client, auth_headers):
    auth_headers("bala@example.com")  # fixture's fixed password: correct-horse-battery-staple
    response = client.post("/auth/login", json={"email": "bala@example.com", "password": "correct-horse-battery-staple"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_with_wrong_password_rejected(client, auth_headers):
    auth_headers("chitra@example.com")
    response = client.post("/auth/login", json={"email": "chitra@example.com", "password": "wrong-pass"})
    assert response.status_code == 401


def test_me_requires_a_valid_token(client, auth_headers):
    headers = auth_headers("devi@example.com")
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "devi@example.com"


def test_me_rejects_missing_token(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_update_profile_changes_editable_fields(client, auth_headers):
    headers = auth_headers("profile1@example.com")
    response = client.patch("/auth/me", headers=headers, json={"name": "New Name", "phone_number": "+911111111111"})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New Name"
    assert body["phone_number"] == "+911111111111"


def test_update_profile_cannot_change_persona(client, auth_headers):
    headers = auth_headers("profile2@example.com")
    # persona isn't even a field on UserProfileUpdate - extra fields are
    # silently ignored by pydantic, not an error, so this just proves it
    # has no effect rather than expecting a 422.
    response = client.patch("/auth/me", headers=headers, json={"name": "Still Driver", "persona": "city_admin"})
    assert response.status_code == 200
    assert response.json()["persona"] == "individual_driver"


def test_change_password_with_correct_current_password(client, auth_headers):
    email = "pwchange1@example.com"
    headers = auth_headers(email)  # fixture's fixed password: correct-horse-battery-staple
    response = client.post("/auth/change-password", headers=headers, json={
        "current_password": "correct-horse-battery-staple", "new_password": "new-secure-pass-123",
    })
    assert response.status_code == 204

    old_login = client.post("/auth/login", json={"email": email, "password": "correct-horse-battery-staple"})
    assert old_login.status_code == 401
    new_login = client.post("/auth/login", json={"email": email, "password": "new-secure-pass-123"})
    assert new_login.status_code == 200


def test_change_password_rejects_wrong_current_password(client, auth_headers):
    headers = auth_headers("pwchange2@example.com")
    response = client.post("/auth/change-password", headers=headers, json={
        "current_password": "totally-wrong", "new_password": "new-secure-pass-123",
    })
    assert response.status_code == 401


def test_change_password_blocked_for_google_accounts(client, db_session):
    from app.auth import create_access_token, hash_password
    from app.models import User
    import secrets

    user = User(
        name="Google User", email="googleuser@example.com", hashed_password=hash_password(secrets.token_urlsafe(32)),
        persona="individual_driver", dpdp_consent_flag=True, email_verified=True, auth_provider="google",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.persona)}"}

    response = client.post("/auth/change-password", headers=headers, json={
        "current_password": "irrelevant", "new_password": "new-secure-pass-123",
    })
    assert response.status_code == 400
