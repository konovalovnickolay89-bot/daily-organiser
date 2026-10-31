AUTH_SECRET = "test-secret-value-0123456789"
SESSION_SECRET = "test-session-secret-0123456789"


def login(client, password: str = AUTH_SECRET):
    response = client.post("/api/auth/login", json={"password": password})
    assert response.status_code == 200, response.text
    return response
