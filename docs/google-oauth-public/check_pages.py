#!/usr/bin/env python3
"""Check the publication HTML. No network. No secrets are read from the environment."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
PAGES = ("index.html", "privacy.html", "terms.html")
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
        if PROTECTED not in text:
            failures.append(f"{name}: protected app host is not mentioned")
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
