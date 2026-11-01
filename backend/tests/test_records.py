from datetime import date, timedelta


def test_health_and_openapi(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "database": "ok"}

    paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/tasks",
        "/commitments",
        "/events",
        "/action-requests",
        "/brief/morning",
        "/approvals",
        "/system/pause",
        "/system/unpause",
    ):
        assert path in paths


def test_starts_without_demo_data_when_seed_is_off(client):
    assert client.get("/tasks").json()["items"] == []
    assert client.get("/commitments").json()["items"] == []
    assert client.get("/events").json()["items"] == []
    assert client.get("/action-requests").json()["items"] == []


def test_task_crud_and_today_scope(client):
    today = date.fromisoformat(client.get("/system").json()["house_date"])
    created = client.post(
        "/tasks",
        json={"title": "  Put the bins out  ", "due_on": today.isoformat(), "priority": "high"},
    )
    assert created.status_code == 201
    task = created.json()
    assert task["title"] == "Put the bins out"
    assert task["owner"] == "Nick"
    assert task["status"] == "todo"
    task_id = task["id"]

    overdue = client.post(
        "/tasks",
        json={
            "title": "Replace the hallway bulb",
            "due_on": (today - timedelta(days=1)).isoformat(),
            "status": "doing",
            "priority": "medium",
        },
    ).json()
    future = client.post(
        "/tasks",
        json={"title": "Book the boiler service", "due_on": (today + timedelta(days=5)).isoformat()},
    ).json()
    done = client.post(
        "/tasks",
        json={"title": "Water the houseplants", "due_on": today.isoformat(), "status": "done"},
    ).json()

    today_titles = [item["title"] for item in client.get("/tasks?scope=today").json()["items"]]
    assert today_titles == ["Replace the hallway bulb", "Put the bins out"]
    assert future["title"] not in today_titles
    assert done["title"] not in today_titles

    fetched = client.get(f"/tasks/{task_id}")
    assert fetched.status_code == 200
    updated = client.patch(f"/tasks/{task_id}", json={"status": "doing", "detail": "Green bin."})
    assert updated.status_code == 200
    assert updated.json()["status"] == "doing"
    assert updated.json()["detail"] == "Green bin."

    high = client.get("/tasks?priority=high").json()["items"]
    assert [item["id"] for item in high] == [task_id]

    deleted = client.delete(f"/tasks/{task_id}")
    assert deleted.status_code == 204
    assert client.get(f"/tasks/{task_id}").status_code == 404


def test_task_validation(client):
    missing = client.post("/tasks", json={"title": "   "})
    assert missing.status_code == 422
    bad = client.post("/tasks", json={"title": "Bins", "priority": "urgent"})
    assert bad.status_code == 422


def test_commitment_crud(client):
    created = client.post(
        "/commitments",
        json={"title": "Return the spare key to next door", "owner": "Nick"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "open"
    kept = client.patch(f"/commitments/{body['id']}", json={"status": "kept"})
    assert kept.json()["status"] == "kept"
    open_items = client.get("/commitments?status=open").json()["items"]
    assert open_items == []
    assert client.delete(f"/commitments/{body['id']}").status_code == 204
    assert client.get(f"/commitments/{body['id']}").status_code == 404


def test_event_crud(client):
    created = client.post(
        "/events",
        json={"kind": "note", "title": "Milk is low", "body": "Nothing has been ordered.", "owner": "Nick"},
    )
    assert created.status_code == 201
    event_id = created.json()["id"]
    listed = client.get("/events?kind=note").json()["items"]
    assert [item["id"] for item in listed] == [event_id]
    updated = client.patch(f"/events/{event_id}", json={"body": "Still nothing ordered."})
    assert updated.json()["body"] == "Still nothing ordered."
    assert client.delete(f"/events/{event_id}").status_code == 204
    assert client.get(f"/events/{event_id}").status_code == 404


def test_action_request_crud_cannot_apply_an_effect(client):
    created = client.post(
        "/action-requests",
        json={"title": "Evening shop list", "mode": "prepare", "detail": "Nothing will be bought."},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "pending"
    assert body["effect_applied"] is False
    updated = client.patch(
        f"/action-requests/{body['id']}",
        json={"status": "approved", "effect_applied": True},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "approved"
    assert updated.json()["effect_applied"] is False
    assert client.get("/action-requests?mode=prepare").json()["items"][0]["id"] == body["id"]
    assert client.delete(f"/action-requests/{body['id']}").status_code == 204
