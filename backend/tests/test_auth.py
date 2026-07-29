def test_register_returns_token(client):
    response = client.post("/auth/register", json={
        "name": "Asha", "email": "asha@example.com", "password": "hunter2pass", "persona": "individual_driver",
    })
    assert response.status_code == 201
    assert "access_token" in response.json()


def test_register_duplicate_email_conflicts(client):
    payload = {"name": "Asha", "email": "dup@example.com", "password": "hunter2pass", "persona": "individual_driver"}
    first = client.post("/auth/register", json=payload)
    assert first.status_code == 201
    second = client.post("/auth/register", json=payload)
    assert second.status_code == 409


def test_login_with_correct_password_succeeds(client):
    client.post("/auth/register", json={
        "name": "Bala", "email": "bala@example.com", "password": "correct-pass", "persona": "fleet_operator",
    })
    response = client.post("/auth/login", json={"email": "bala@example.com", "password": "correct-pass"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_with_wrong_password_rejected(client):
    client.post("/auth/register", json={
        "name": "Chitra", "email": "chitra@example.com", "password": "correct-pass", "persona": "individual_driver",
    })
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
