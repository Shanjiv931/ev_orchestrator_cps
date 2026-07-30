def test_register_returns_pending_registration(client):
    response = client.post("/auth/register", json={
        "name": "Asha", "email": "asha@example.com", "password": "hunter2pass", "persona": "individual_driver",
    })
    assert response.status_code == 201
    body = response.json()
    assert "pending_registration_id" in body
    assert body["email"] == "asha@example.com"


def test_registering_same_unverified_email_twice_is_allowed(client):
    # No row is persisted until OTP verification (see app/routers/auth.py),
    # so there's no real account yet for a second attempt to conflict with -
    # each gets its own independent pending registration.
    payload = {"name": "Asha", "email": "dup@example.com", "password": "hunter2pass", "persona": "individual_driver"}
    first = client.post("/auth/register", json=payload)
    second = client.post("/auth/register", json=payload)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["pending_registration_id"] != second.json()["pending_registration_id"]


def test_registering_an_already_verified_email_conflicts(client, auth_headers):
    auth_headers("already-verified@example.com")
    response = client.post("/auth/register", json={
        "name": "X", "email": "already-verified@example.com", "password": "hunter2pass", "persona": "individual_driver",
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
