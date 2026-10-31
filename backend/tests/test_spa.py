from pathlib import Path

from organiser.spa import path_escapes, resolve_dist_file


def test_resolve_dist_file_stays_inside(tmp_path: Path):
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    index = dist / "index.html"
    index.write_text("index", encoding="utf-8")
    script = assets / "app.js"
    script.write_text("js", encoding="utf-8")

    assert resolve_dist_file(dist, "index.html") == index.resolve()
    assert resolve_dist_file(dist, "assets/app.js") == script.resolve()
    assert resolve_dist_file(dist, "missing") is None
    assert resolve_dist_file(dist, "../.env") is None
    assert path_escapes(dist, "../.env") is True
    assert path_escapes(dist, "index.html") is False


def test_built_ui_is_served_and_api_still_wins(tmp_path, monkeypatch, make_client):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><p>built ui</p>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    monkeypatch.setattr("organiser.main.FRONTEND_DIST", dist)

    with make_client() as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "built ui" in page.text
        assert client.get("/today").text == page.text
        asset = client.get("/assets/app.js")
        assert asset.status_code == 200
        assert "console.log" in asset.text
        assert client.get("/assets/missing.js").status_code == 404
        assert client.get("/api/health").json() == {"ok": True}
        assert client.get("/api/does-not-exist").status_code == 404


def test_root_without_frontend_build_is_404(tmp_path, monkeypatch, make_client):
    monkeypatch.setattr("organiser.main.FRONTEND_DIST", tmp_path / "missing-dist")
    with make_client() as client:
        assert client.get("/").status_code == 404
