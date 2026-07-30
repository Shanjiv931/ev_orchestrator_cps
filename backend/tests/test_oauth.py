def test_google_sign_in_returns_501_when_not_configured(client):
    response = client.post("/oauth/google", json={"id_token": "fake"})
    assert response.status_code == 501


def test_simulated_apple_sign_in_creates_account(client):
    response = client.post("/oauth/apple/simulated", json={"simulated_apple_id": "abc123", "name": "Apple Test User"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_simulated_apple_sign_in_is_idempotent_for_same_id(client):
    r1 = client.post("/oauth/apple/simulated", json={"simulated_apple_id": "same-id", "name": "User A"})
    r2 = client.post("/oauth/apple/simulated", json={"simulated_apple_id": "same-id", "name": "User A"})

    me1 = client.get("/auth/me", headers={"Authorization": f"Bearer {r1.json()['access_token']}"})
    me2 = client.get("/auth/me", headers={"Authorization": f"Bearer {r2.json()['access_token']}"})
    assert me1.json()["id"] == me2.json()["id"]


def test_simulated_apple_user_has_apple_simulated_auth_provider(client):
    response = client.post("/oauth/apple/simulated", json={"simulated_apple_id": "provider-check", "name": "User B"})
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert me.json()["auth_provider"] == "apple-simulated"
