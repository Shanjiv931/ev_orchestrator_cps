def test_google_sign_in_returns_501_when_not_configured(client):
    response = client.post("/oauth/google", json={"id_token": "fake"})
    assert response.status_code == 501
