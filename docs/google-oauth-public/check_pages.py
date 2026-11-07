#!/usr/bin/env python3
"""Check the publication HTML. No network. No secrets are read from the environment."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
PAGES = ("index.html", "privacy.html", "terms.html", "404.html")
# Paths that exist as files. "/" is index.html.
ASSETS = {"/", "/index.html", "/privacy.html", "/terms.html", "/404.html"}
# Absent API paths. These are not files and must not be served as the app.
ABSENT = (
    "/health",
    "/brief/morning",
    "/docs",
    "/assets/",
    "/assets/index.js",
    "/api",
    "/system/facts",
    "/favicon.ico",
)
EMAIL = "mykolakonovalov@gmail.com"
MAILTO = f"mailto:{EMAIL}"
SUPPORT = (
    f'The public support email for Daily Organiser bot is <a href="{MAILTO}">{EMAIL}</a>. '
    "The operator is Mykola Konovalov."
)
PROTECTED = "organiser.apidiscoverysolution.uk"
PRIVACY_URL = "https://organiser-info.apidiscoverysolution.uk/privacy.html"
SCOPES = (
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
)


def pages_status(path: str, *, has_404: bool) -> int:
    """Model of Cloudflare Pages, not a request to a live host.

    Serving Pages (last updated 10 Oct 2026): with no top-level 404.html, Pages
    treats the project as a single-page app and serves ``/`` for a path that is
    not a static asset. With a top-level 404.html, it serves that not-found page
    instead. This model uses HTTP 404 for the not-found case and HTTP 200 for
    the SPA case. The Pages paragraph does not print the SPA status number; the
    Workers static-assets page documents the same split as 200 and 404.
    """
    asset = path.split("?", 1)[0]
    if asset in ASSETS:
        return 200
    if has_404:
        return 404
    return 200


def pages_model_failures() -> list[str]:
    failures: list[str] = []
    if not (ROOT / "404.html").is_file():
        return ["404.html: missing, so the documented SPA fallback would apply"]
    for path in ("/", "/index.html", "/privacy.html", "/terms.html", "/404.html"):
        if pages_status(path, has_404=True) != 200:
            failures.append(f"pages model: {path} should be 200")
    for path in ABSENT:
        if pages_status(path, has_404=True) != 404:
            failures.append(f"pages model: {path} should be 404 when 404.html exists")
        if pages_status(path, has_404=False) != 200:
            failures.append(f"pages model: {path} should be 200 SPA fallback without 404.html")
    return failures


def main() -> int:
    failures: list[str] = []
    for name in PAGES:
        text = (ROOT / name).read_text(encoding="utf-8")
        lower = text.lower()
        if "<script" in lower:
            failures.append(f"{name}: contains a script")
        if re.search(r"<form\b", text, re.I):
            failures.append(f"{name}: contains a form")
        if re.search(r"<input\b|<button\b|<textarea\b", text, re.I):
            failures.append(f"{name}: contains a control")
        if "Draft for approval" in text or "Approval needed" in text:
            failures.append(f"{name}: still has a draft or unapproved-contact banner")
        if SUPPORT not in text:
            failures.append(f"{name}: support sentence missing or different")
        if text.count(MAILTO) != 1:
            failures.append(f"{name}: expected one mailto, found {text.count(MAILTO)}")
        other = set(re.findall(r"mailto:([^\"']+)", text)) - {EMAIL}
        if other:
            failures.append(f"{name}: unexpected mailto {other}")
        if "Daily Organiser bot" not in text:
            failures.append(f"{name}: missing consent-screen name")
        if re.search(rf'href="[^"]*{re.escape(PROTECTED)}', text):
            failures.append(f"{name}: protected app host is a link")
        if name != "404.html" and PROTECTED not in text:
            failures.append(f"{name}: protected app host is not mentioned")
        if name == "404.html":
            if "Page not found" not in text:
                failures.append("404.html: missing not-found heading")
            if PROTECTED in text:
                failures.append("404.html: mentions the protected app host")
    failures.extend(pages_model_failures())
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    privacy = (ROOT / "privacy.html").read_text(encoding="utf-8")
    if 'href="privacy.html"' not in index:
        failures.append("index.html: privacy link missing")
    if PRIVACY_URL not in index or PRIVACY_URL not in privacy:
        failures.append("privacy URL is not on both the homepage and the privacy page")
    for scope in SCOPES:
        if scope not in privacy:
            failures.append(f"privacy.html: missing {scope}")
    if "voxtral-mini-transcribe-3" not in privacy:
        failures.append("privacy.html: missing the current transcription default")
    if failures:
        print("\n".join(failures))
        return 1
    print(f"ok: {', '.join(PAGES)}")
    print("pages model: absent API paths are HTTP 404 when 404.html is present, and HTTP 200 without it. This is not a live request.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
