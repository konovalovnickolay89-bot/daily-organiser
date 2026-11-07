"""Hybrid memory search: full text, cosine when a key is set, and redaction."""

from datetime import timedelta

from agent_fakes import london
from organiser.agent.memory import embed_query
from organiser.config import get_settings
from organiser.models import MEMORY_EMBEDDING_DIM, MemoryItem


def _line(text: str, when, *, pinned: bool = False, embedding: list[float] | None = None) -> MemoryItem:
    return MemoryItem(
        kind="fact",
        text=text,
        source="manual",
        created_at=when,
        pinned=pinned,
        embedding=embedding,
    )


def test_search_ranks_a_pin_over_a_close_newer_line_and_ignores_noise(client, db, house_clock, monkeypatch):
    house_clock["now"] = london(2026, 11, 6, 8, 0)
    now = london(2026, 11, 6, 8, 0)

    def refuse(text: str):
        raise AssertionError(f"embed was called for {text}")

    monkeypatch.setattr("organiser.agent.memory.embed_query", refuse)
    db.add(_line("oat milk stays in the door", now - timedelta(days=2), pinned=True))
    db.add(_line("oat milk stays in the door", now - timedelta(days=1), pinned=False))
    db.add(_line("bins go out every Tuesday", now, pinned=True))
    db.commit()

    found = client.get("/memory/search", params={"q": "oat milk"})
    assert found.status_code == 200
    body = found.json()
    assert body["mode"] == "fts"
    assert [item["pinned"] for item in body["items"]] == [True, False]
    assert all(item["text"] == "oat milk stays in the door" for item in body["items"])
    assert "embedding" not in found.text
    assert embed_query("oat milk") is None


def test_search_falls_back_to_full_text_without_a_key_and_uses_cosine_with_one(client, db, house_clock, monkeypatch):
    house_clock["now"] = london(2026, 11, 6, 8, 0)
    now = london(2026, 11, 6, 8, 0)
    close = [1.0] + [0.0] * (MEMORY_EMBEDDING_DIM - 1)
    far = [0.0, 1.0] + [0.0] * (MEMORY_EMBEDDING_DIM - 2)
    db.add(_line("the spare fuse is in the cupboard", now, embedding=close))
    db.add(_line("oat milk stays in the door", now, embedding=far))
    db.commit()

    plain = client.get("/memory/search", params={"q": "oat milk"})
    assert plain.json()["mode"] == "fts"
    assert [item["text"] for item in plain.json()["items"]] == ["oat milk stays in the door"]

    monkeypatch.setenv("MISTRAL_API_KEY", "test-key-not-real")
    get_settings.cache_clear()
    seen: list[str] = []

    def fake_embed(text: str):
        seen.append(text)
        return close

    monkeypatch.setattr("organiser.agent.memory.embed_query", fake_embed)
    try:
        hybrid = client.get("/memory/search", params={"q": "oat milk"})
        assert hybrid.status_code == 200
        body = hybrid.json()
        assert body["mode"] == "hybrid"
        assert seen == ["oat milk"]
        texts = [item["text"] for item in body["items"]]
        assert "oat milk stays in the door" in texts
        assert "the spare fuse is in the cupboard" in texts
        assert "test-key-not-real" not in hybrid.text
    finally:
        get_settings.cache_clear()


def test_search_redacts_a_postcode_and_refuses_work(client, db, house_clock, monkeypatch, caplog):
    house_clock["now"] = london(2026, 11, 6, 8, 0)
    now = london(2026, 11, 6, 8, 0)
    db.add(_line("oat milk stays in the door", now))
    db.commit()
    monkeypatch.setenv("HOUSE_POSTCODE", "SW1A 1AA")
    monkeypatch.setenv("HOUSE_LAT", "51.501")
    monkeypatch.setenv("HOUSE_LON", "-0.142")
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key-not-real")
    get_settings.cache_clear()
    seen: list[str] = []

    def fake_embed(text: str):
        seen.append(text)
        return None

    monkeypatch.setattr("organiser.agent.memory.embed_query", fake_embed)
    try:
        with caplog.at_level("DEBUG"):
            found = client.get("/memory/search", params={"q": "oat milk SW1A 1AA 51.501,-0.142"})
        assert found.status_code == 200
        assert found.json()["mode"] == "fts"
        assert [item["text"] for item in found.json()["items"]] == ["oat milk stays in the door"]
        assert seen and "SW1A" not in seen[0]
        assert "51.501" not in seen[0]
        assert "-0.142" not in seen[0]
        assert "SW1A 1AA" not in caplog.text
        blocked = client.get("/memory/search", params={"q": "the Hilton guest likes oat milk"})
        assert blocked.json()["items"] == []
    finally:
        get_settings.cache_clear()
