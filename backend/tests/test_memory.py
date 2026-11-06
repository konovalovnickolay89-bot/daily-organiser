"""Remember, forget, recall, and the house boundary for memory."""

import json
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from agent_fakes import call, london, say

from organiser.agent.context import MEMORY_LIMIT, build_context
from organiser.agent.memory import classify_kind, embed_query, parse_memory_intent, redact_for_model
from organiser.agent.mistral import MistralClient, MistralUnavailable
from organiser.agent.runner import feed_packet
from organiser.config import get_settings
from organiser.models import Event, MemoryItem
from organiser.timeutil import utcnow


OUTSIDE = [
    "The Hilton guest wants a late checkout",
    "A colleague asked me to cover",
    "My employer moved the meeting",
    "The hotel booking is Thursday",
    "Remember my work email is on the desk",
    "Payroll is done at the workplace",
]


def test_kind_and_intent():
    assert parse_memory_intent("remember the milk stays in the door").text == "the milk stays in the door"
    assert parse_memory_intent("Please remember that I prefer tea.").action == "remember"
    assert parse_memory_intent("forget about the milk").action == "forget"
    assert parse_memory_intent("buy oat milk") is None
    assert classify_kind("I prefer tea") == "preference"
    assert classify_kind("bins go out every Tuesday") == "routine"
    assert classify_kind("the milk is in the door") == "fact"


@pytest.mark.parametrize("text", OUTSIDE)
def test_outside_text_is_never_stored(client, text):
    created = client.post("/memory", json={"kind": "fact", "text": text})
    assert created.status_code == 422
    assert created.json()["detail"] == "Not for the house log."
    remembered = client.post("/agent/feed", json={"text": f"remember {text}"})
    assert remembered.status_code == 422
    assert client.get("/memory").json()["items"] == []
    forgotten = client.post("/agent/feed", json={"text": f"forget {text}"})
    assert forgotten.status_code == 422


def test_remember_waits_for_apply_and_does_not_call_mistral(client, house_clock, mistral):
    house_clock["now"] = london(2026, 11, 6, 8, 0)
    fake = mistral([say("This must not run.")])
    response = client.post("/agent/feed", json={"text": "remember the milk stays in the door"})
    assert response.status_code == 200
    body = response.json()
    assert fake.calls == []
    assert body["reply"] == "Waiting for Apply. Nothing is saved yet."
    assert body["proposals"][0]["summary"] == "Remember: the milk stays in the door"
    assert body["proposals"][0]["action"] == "remember"
    assert client.get("/memory").json()["items"] == []

    dismissed = client.post("/agent/feed", json={"text": "remember the bins go out every Tuesday"})
    card = dismissed.json()["proposals"][0]
    assert client.post(f"/agent/proposals/{card['id']}/dismiss").status_code == 200
    assert client.get("/memory").json()["items"] == []

    kept = body["proposals"][0]
    applied = client.post(f"/agent/proposals/{kept['id']}/apply")
    assert applied.status_code == 200
    items = client.get("/memory").json()["items"]
    assert [item["text"] for item in items] == ["the milk stays in the door"]
    assert items[0]["kind"] == "fact"
    assert items[0]["source"] == "remember"
    from organiser.db import get_sessionmaker

    session = get_sessionmaker()()
    try:
        events = session.scalars(select(Event).order_by(Event.recorded_at.desc())).all()
    finally:
        session.close()
    assert any(event.title == "Remembered: the milk stays in the door" for event in events)


def test_remember_does_not_spend_a_mistral_run(client, house_clock):
    house_clock["now"] = london(2026, 11, 6, 8, 0)
    before = client.get("/agent").json()["runs_left_today"]
    assert client.post("/agent/feed", json={"text": "remember I prefer tea in the morning"}).status_code == 200
    assert client.get("/agent").json()["runs_left_today"] == before


def test_paused_house_does_not_remember(client):
    assert client.post("/system/pause").status_code == 200
    response = client.post("/agent/feed", json={"text": "remember the spare key is in the bowl"})
    assert response.status_code == 409
    assert client.get("/memory").json()["items"] == []


def test_forget_deletes_only_what_is_confirmed_and_writes_an_audit_line(client, db):
    first = client.post("/agent/feed", json={"text": "remember the milk stays in the door"})
    second = client.post("/agent/feed", json={"text": "remember the bins go out on Tuesday"})
    client.post(f"/agent/proposals/{first.json()['proposals'][0]['id']}/apply")
    client.post(f"/agent/proposals/{second.json()['proposals'][0]['id']}/apply")

    forget = client.post("/agent/feed", json={"text": "forget milk"})
    card = forget.json()["proposals"][0]
    assert card["action"] == "forget"
    assert [match["text"] for match in card["matches"]] == ["the milk stays in the door"]
    assert client.get("/memory").json()["items"]

    milk_id = card["matches"][0]["id"]
    bins = next(item for item in client.get("/memory").json()["items"] if "bins" in item["text"])
    applied = client.post(
        f"/agent/proposals/{card['id']}/apply",
        json={"memory_ids": [milk_id, bins["id"]]},
    )
    assert applied.status_code == 200
    left = client.get("/memory").json()["items"]
    assert [item["text"] for item in left] == ["the bins go out on Tuesday"]
    titles = [row.title for row in db.scalars(select(Event)).all()]
    assert any(title.startswith("Forgot: the milk stays in the door") for title in titles)
    assert not any("bins" in title and title.startswith("Forgot:") for title in titles)


def test_not_now_forgets_nothing(client):
    made = client.post("/agent/feed", json={"text": "remember the milk stays in the door"})
    client.post(f"/agent/proposals/{made.json()['proposals'][0]['id']}/apply")
    forget = client.post("/agent/feed", json={"text": "forget the milk"})
    card = forget.json()["proposals"][0]
    assert client.post(f"/agent/proposals/{card['id']}/dismiss").status_code == 200
    assert len(client.get("/memory").json()["items"]) == 1


def test_recall_fills_ten_by_words_and_marks_them_used(db, house_clock):
    house_clock["now"] = london(2026, 11, 6, 8, 0)
    now = london(2026, 11, 6, 8, 0)
    for index in range(12):
        db.add(
            MemoryItem(
                kind="fact",
                text=f"milk note {index} stays in the door",
                source="manual",
                created_at=now - timedelta(days=index),
                pinned=index == 3,
            )
        )
    db.add(
        MemoryItem(
            kind="routine",
            text="the piano is tuned in spring",
            source="manual",
            created_at=now,
        )
    )
    db.flush()
    slot = build_context(db, purpose="smart_add", now=now, query="where is the milk").memory
    assert slot.limit == MEMORY_LIMIT == 10
    assert len(slot.items) == 10
    assert all("milk" in item.text for item in slot.items)
    assert all(item.kind == "fact" for item in slot.items)
    pinned = db.scalars(select(MemoryItem).where(MemoryItem.pinned.is_(True))).one()
    assert pinned.last_used_at == now


def test_similarity_outranks_a_newer_unrelated_line(db, monkeypatch):
    now = london(2026, 11, 6, 9, 0)
    near = [1.0, *([0.0] * 1023)]
    far = [0.0, 1.0, *([0.0] * 1022)]
    db.add(
        MemoryItem(
            kind="fact",
            text="alpha",
            source="manual",
            created_at=now - timedelta(days=40),
            embedding=near,
        )
    )
    db.add(
        MemoryItem(
            kind="fact",
            text="beta",
            source="manual",
            created_at=now,
            embedding=far,
        )
    )
    db.flush()
    monkeypatch.setattr("organiser.agent.memory.embed_query", lambda text: near)
    slot = build_context(db, purpose="smart_add", now=now, query="something else").memory
    assert [item.text for item in slot.items] == ["alpha"]


def test_keyword_fallback_when_embeddings_are_unavailable(db, monkeypatch):
    now = london(2026, 11, 6, 9, 0)
    db.add(MemoryItem(kind="fact", text="the milk stays in the door", source="manual", created_at=now))
    db.add(
        MemoryItem(
            kind="routine",
            text="the bins go out on Tuesday",
            source="manual",
            created_at=now + timedelta(minutes=1),
        )
    )
    db.flush()
    monkeypatch.setattr("organiser.agent.memory.embed_query", lambda text: None)
    slot = build_context(db, purpose="smart_add", now=now, query="milk").memory
    assert [item.text for item in slot.items] == ["the milk stays in the door"]


def test_catch_up_context_uses_the_open_task(db):
    now = london(2026, 11, 6, 8, 0)
    from organiser.models import Task

    db.add(Task(title="Put the bins out", status="todo", priority="medium", owner="Nick"))
    db.add(MemoryItem(kind="routine", text="bins go out every Tuesday", source="remember", created_at=now))
    db.add(MemoryItem(kind="fact", text="the piano is tuned in spring", source="remember", created_at=now))
    db.flush()
    slot = build_context(db, purpose="catch_up", now=now).memory
    assert [item.text for item in slot.items] == ["bins go out every Tuesday"]


def test_context_and_embeddings_never_carry_a_postcode_or_coordinate(db, monkeypatch):
    monkeypatch.setenv("HOUSE_POSTCODE", "SW1A 1AA")
    monkeypatch.setenv("HOUSE_LAT", "51.5074")
    monkeypatch.setenv("HOUSE_LON", "-0.1278")
    get_settings.cache_clear()
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]})

    monkeypatch.setattr(
        "organiser.agent.memory.MistralClient",
        lambda *args, **kwargs: MistralClient("test-key", "https://api.mistral.test", 5, transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key-not-real")
    get_settings.cache_clear()
    now = london(2026, 11, 6, 8, 0)
    db.add(
        MemoryItem(
            kind="fact",
            text="The door code is SW1A 1AA near 51.5074 and -0.1278 and the bins are Tuesday",
            source="manual",
            created_at=now,
            embedding=[1.0, *([0.0] * 1023)],
        )
    )
    db.flush()
    context = build_context(db, purpose="smart_add", now=now, query="bins near SW1A 1AA")
    dumped = context.model_dump_json()
    for secret in ("SW1A 1AA", "SW1A1AA", "51.5074", "-0.1278"):
        assert secret not in dumped
    packet = feed_packet(now, "Europe/London", 3, "need filters", context)
    assert "\n\nContext:\n" in packet
    for secret in ("SW1A", "51.5074", "-0.1278"):
        assert secret not in packet.split("\n\nContext:\n", 1)[1]
    assert seen
    sent = json.dumps(seen)
    for secret in ("SW1A", "51.5074", "-0.1278"):
        assert secret not in sent
    get_settings.cache_clear()


def test_embed_client_refuses_a_location():
    client = MistralClient("test-key", "https://api.mistral.test", 5, transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    with pytest.raises(MistralUnavailable):
        client.embed("the code is SW1A 1AA")
    with pytest.raises(MistralUnavailable):
        client.embed("meet at 51.5074")


def test_redact_removes_the_configured_place(monkeypatch):
    monkeypatch.setenv("HOUSE_POSTCODE", "N1 1AA")
    monkeypatch.setenv("HOUSE_LAT", "51.5000")
    monkeypatch.setenv("HOUSE_LON", "-0.1000")
    get_settings.cache_clear()
    assert "N1" not in redact_for_model("home is N1 1AA at 51.5000, -0.1000")
    get_settings.cache_clear()


def test_smart_add_card_reports_how_many_memories_were_used(client, db, house_clock, mistral):
    house_clock["now"] = london(2026, 11, 6, 8, 0)
    db.add(
        MemoryItem(
            kind="fact",
            text="the milk stays in the door",
            source="remember",
            created_at=utcnow(),
        )
    )
    db.commit()
    fake = mistral(
        [
            call(
                "propose_change",
                {"action": "create_task", "changes": {"title": "Buy more milk"}, "reason": "The door is the usual place."},
            )
        ],
        [say("One proposal.")],
    )
    response = client.post("/agent/feed", json={"text": "we are low on milk"})
    assert response.status_code == 200
    packet = fake.calls[0][2]
    context = json.loads(packet.split("\n\nContext:\n", 1)[1])
    assert context["memory"]["items"][0]["text"] == "the milk stays in the door"
    assert response.json()["proposals"][0]["memories_used"] == 1


def test_export_is_json_without_embeddings(client):
    created = client.post("/memory", json={"kind": "preference", "text": "I prefer the blue mug"})
    assert created.status_code == 201
    assert created.json()["source"] == "manual"
    exported = client.get("/memory/export")
    assert exported.status_code == 200
    body = exported.json()
    assert body["items"][0]["text"] == "I prefer the blue mug"
    assert "embedding" not in json.dumps(body)
    assert "exported_at" in body


def test_settings_forget_confirms_with_an_audit_line(client, db):
    created = client.post("/memory", json={"kind": "fact", "text": "the spare key is in the bowl"})
    item_id = created.json()["id"]
    assert client.patch(f"/memory/{item_id}", json={"pinned": True}).json()["pinned"] is True
    listed = client.get("/memory", params={"q": "spare"})
    assert listed.json()["items"][0]["id"] == item_id
    assert client.delete(f"/memory/{item_id}").status_code == 200
    assert client.get("/memory").json()["items"] == []
    titles = [row.title for row in db.scalars(select(Event)).all()]
    assert any(title.startswith("Forgot: the spare key is in the bowl") for title in titles)


def test_get_memory_does_not_embed(client, monkeypatch):
    def boom(text):
        raise AssertionError(text)

    monkeypatch.setattr("organiser.routes.memory.embed_query", boom)
    monkeypatch.setattr("organiser.agent.memory.embed_query", boom)
    assert client.get("/memory").status_code == 200
    assert client.get("/memory/export").status_code == 200
    assert client.get("/agent").status_code == 200


def test_embed_query_without_a_key_is_quiet(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "")
    get_settings.cache_clear()
    assert embed_query("the milk stays in the door") is None
    get_settings.cache_clear()
