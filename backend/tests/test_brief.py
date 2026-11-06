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

    by_key = {section["key"]: section for section in body["sections"]}
    assert by_key["shopping"]["placeholder"] is False
    assert by_key["shopping"]["items"] == []
    assert by_key["shopping"]["summary"] == "Shopping list is empty."
    assert "Diary not connected" in by_key["appointments"]["summary"]
    assert by_key["appointments"]["items"] == []
    assert by_key["weather"]["summary"] == "Weather location is not set."
    assert by_key["weather"]["items"] == []


def test_london_civil_date_on_the_clock_change():
    """A due date is the London civil date, including the spring and autumn changes."""
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    london = ZoneInfo("Europe/London")
    spring = datetime(2026, 3, 29, 1, 30, tzinfo=timezone.utc).astimezone(london)
    autumn = datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc).astimezone(london)
    assert spring.date().isoformat() == "2026-03-29"
    assert autumn.date().isoformat() == "2026-10-25"


def test_due_date_follows_the_house_date_across_the_clock_change(client, monkeypatch):
    from datetime import date

    monkeypatch.setattr("organiser.routes.brief.house_today", lambda tz: date(2026, 3, 29))
    client.post("/tasks", json={"title": "Put the clocks forward", "due_on": "2026-03-29"})
    client.post("/tasks", json={"title": "Leave this until April", "due_on": "2026-04-02"})
    titles = [item["title"] for item in client.get("/brief/morning").json()["sections"][0]["items"]]
    assert "Put the clocks forward" in titles
    assert "Leave this until April" not in titles

    monkeypatch.setattr("organiser.routes.brief.house_today", lambda tz: date(2026, 10, 25))
    client.post("/tasks", json={"title": "Put the clocks back", "due_on": "2026-10-25"})
    titles = [item["title"] for item in client.get("/brief/morning").json()["sections"][0]["items"]]
    assert "Put the clocks back" in titles
    assert "Put the clocks forward" in titles


def test_brief_notes_when_the_house_is_paused(client):
    client.post("/system/pause")
    body = client.get("/brief/morning").json()
    assert body["paused"] is True
    assert body["note"] == "The house is paused. This brief is only a reading."


def _shift(iso_date: str, days: int) -> str:
    from datetime import date

    return (date.fromisoformat(iso_date) + timedelta(days=days)).isoformat()
