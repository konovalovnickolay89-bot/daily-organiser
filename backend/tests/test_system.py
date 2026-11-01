def test_pause_and_unpause(client):
    paused = client.post("/system/pause")
    assert paused.status_code == 200
    body = paused.json()
    assert body["paused"] is True
    assert body["activity"] == "paused"
    assert body["status_text"] == "Paused"

    again = client.post("/system/pause")
    assert again.status_code == 200
    assert again.json()["paused"] is True

    titles = [item["title"] for item in client.get("/events?kind=system").json()["items"]]
    assert titles.count("House paused") == 1

    resumed = client.post("/system/unpause")
    assert resumed.status_code == 200
    quiet = resumed.json()
    assert quiet["paused"] is False
    assert quiet["activity"] == "quiet"
    assert quiet["status_text"] == "All quiet"

    state = client.get("/system")
    assert state.json()["paused"] is False
    titles = [item["title"] for item in client.get("/events?kind=system").json()["items"]]
    assert "House resumed" in titles


def test_invalid_approval_filter(client):
    response = client.get("/approvals?status=later")
    assert response.status_code == 422
