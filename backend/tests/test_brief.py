from datetime import timedelta


def test_morning_brief_composes_live_items_and_placeholders(client):
    today = client.get("/system").json()["house_date"]
    yesterday = _shift(today, -1)
    later = _shift(today, 5)
    client.post("/tasks", json={"title": "Put the bins out", "due_on": today, "priority": "high"})
    client.post("/tasks", json={"title": "Replace the hallway bulb", "due_on": yesterday, "status": "doing"})
    client.post("/tasks", json={"title": "Book the boiler service", "due_on": later})
    client.post("/tasks", json={"title": "Water the houseplants", "due_on": today, "status": "done"})
    client.post("/commitments", json={"title": "Return the spare key to next door"})
    client.post("/commitments", json={"title": "Take the library books back", "status": "kept"})

    brief = client.get("/brief/morning")
    assert brief.status_code == 200
    body = brief.json()
    assert body["title"] == "Morning brief"
    assert body["house_date"] == today
    assert body["paused"] is False
    assert [section["key"] for section in body["sections"]] == [
        "tasks",
        "commitments",
        "appointments",
        "shopping",
        "weather",
    ]

    tasks = body["sections"][0]
    assert tasks["placeholder"] is False
    assert [item["title"] for item in tasks["items"]] == [
        "Replace the hallway bulb",
        "Put the bins out",
    ]
    assert "Overdue" in tasks["items"][0]["meta"]
    assert "Due today" in tasks["items"][1]["meta"]

    commitments = body["sections"][1]
    assert [item["title"] for item in commitments["items"]] == ["Return the spare key to next door"]

    placeholders = {section["key"]: section for section in body["sections"] if section["placeholder"]}
    assert set(placeholders) == {"appointments", "shopping", "weather"}
    assert placeholders["shopping"]["items"] == []
    assert "Nothing is ordered" in placeholders["shopping"]["summary"]
    assert "No diary is connected" in placeholders["appointments"]["summary"]
    assert "Weather is not connected" in placeholders["weather"]["summary"]


def test_brief_notes_when_the_house_is_paused(client):
    client.post("/system/pause")
    body = client.get("/brief/morning").json()
    assert body["paused"] is True
    assert body["note"] == "The house is paused. This brief is only a reading."


def _shift(iso_date: str, days: int) -> str:
    from datetime import date

    return (date.fromisoformat(iso_date) + timedelta(days=days)).isoformat()
