# Google Calendar public pages

Publication text for four HTML files. They are not hosted yet, not wired into the app, and not submitted to Google. Nick approved discovery-system publishing those four files on Cloudflare Pages at `organiser-info`. This repository does not do that publish.

`mykolakonovalov@gmail.com` is the approved public support email for Daily Organiser bot, on the pages and as the consent-screen user-support value. That approval does not create DNS, change Cloudflare, or press Verify or Publish in Google.

The consent-screen name stays **Daily Organiser bot**, the name already entered. These pages use that name.

| File | What it is |
| --- | --- |
| [index.html](index.html) | App description. Publication text for the homepage. |
| [privacy.html](privacy.html) | Privacy policy. Same URL for the consent screen. |
| [terms.html](terms.html) | Terms. No court, liability cap, or warranty. |
| [404.html](404.html) | Not-found page. Stops the Pages single-page-application fallback. |
| [HOSTING-PLAN.md](HOSTING-PLAN.md) | Cloudflare Pages for the four files only. Publish is approved and not done here. |
| [CALENDAR-SETUP.md](CALENDAR-SETUP.md) | Remaining setup steps and which gates are still shut. |
| [IN_APP_NOTICE.md](IN_APP_NOTICE.md) | Proposed in-app privacy link. Not applied. |
| [EVIDENCE.md](EVIDENCE.md) | Source paths and functions, including the PR 27 re-read. |
| [check_pages.py](check_pages.py) | Checks the four HTML files and the documented Pages 404 model. |

Open the HTML from this directory. The pages are self-contained: no script, no form, no analytics, no app bundle.

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```

Then open `http://127.0.0.1:8765/`. That local server is only a way to read the files. It is not the public host.

```bash
python3 docs/google-oauth-public/check_pages.py
```

## Branch

Started from `origin/main` at `d306b57`. Current main `e5ce5d1` (PR 27) is merged in. Open PRs other than this one are not included. History was not rewritten.

## Not done

No DNS, Cloudflare, Access, tunnel, deploy, merge, or push to `main`. No Google, TfL, or Mistral call. No credentials collected. No migration. No data deletion. `organiser.apidiscoverysolution.uk` is unchanged and stays behind Cloudflare Access.

Do not paste the info URLs into Google until the access tests in `HOSTING-PLAN.md` pass.
