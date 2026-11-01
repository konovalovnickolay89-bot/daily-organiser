import pytest


@pytest.mark.parametrize(
    ("mode", "phrase"),
    [
        ("observe", "Nothing further was done."),
        ("advise", "Nothing was sent."),
        ("prepare", "Nothing was gathered or ordered."),
        ("execute", "Execute is not wired"),
    ],
)
def test_approve_records_status_only(client, mode, phrase):
    created = client.post(
        "/action-requests",
        json={"title": f"Decide {mode}", "mode": mode, "owner": "Nick"},
    ).json()
    response = client.post(f"/approvals/{created['id']}/approve")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["effect_applied"] is False
    assert body["effect"]["applied"] is False
    assert phrase in body["effect"]["summary"]
    assert body["resolution"] == body["effect"]["summary"]

    stored = client.get(f"/action-requests/{created['id']}").json()
    assert stored["effect_applied"] is False
    assert stored["status"] == "approved"

    again = client.post(f"/approvals/{created['id']}/approve")
    assert again.status_code == 409
    assert again.json()["detail"] == "This has already been decided."


def test_skip_and_pending_list(client):
    first = client.post("/action-requests", json={"title": "Milk is low", "mode": "observe"}).json()
    second = client.post("/action-requests", json={"title": "Evening shop list", "mode": "prepare"}).json()

    pending = client.get("/approvals").json()["items"]
    assert {item["id"] for item in pending} == {first["id"], second["id"]}
    assert {item["status"] for item in pending} == {"pending"}

    skipped = client.post(f"/approvals/{first['id']}/skip")
    assert skipped.status_code == 200
    assert skipped.json()["status"] == "skipped"
    assert skipped.json()["effect"]["applied"] is False
    assert skipped.json()["effect"]["summary"] == "Skipped. Nothing was done."

    still_pending = client.get("/approvals").json()["items"]
    assert [item["id"] for item in still_pending] == [second["id"]]
    everyone = client.get("/approvals?status=all").json()["items"]
    assert {item["status"] for item in everyone} == {"skipped", "pending"}


def test_unknown_approval(client):
    response = client.post("/approvals/00000000-0000-0000-0000-000000000000/approve")
    assert response.status_code == 404


def test_pause_does_not_turn_a_decision_into_an_effect(client):
    client.post("/system/pause")
    created = client.post("/action-requests", json={"title": "Note the milk", "mode": "observe"}).json()
    response = client.post(f"/approvals/{created['id']}/approve")
    assert response.status_code == 200
    assert response.json()["effect"]["applied"] is False
    assert client.get("/system").json()["paused"] is True
    log = client.get("/events?kind=approval").json()["items"]
    assert log[0]["title"] == "Approved: Note the milk"
    assert "Nothing further was done." in log[0]["body"]
