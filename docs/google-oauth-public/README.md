# Google Calendar public pages (draft)

Drafts for Nick’s approval. They are not published, not wired into the app, and not submitted to Google.

| File | What it is |
| --- | --- |
| [index.html](index.html) | App description. Proposed homepage. |
| [privacy.html](privacy.html) | Privacy policy. Proposed consent-screen privacy URL. |
| [terms.html](terms.html) | Terms draft. Google’s production-homepage rule asks for a terms link. This one is not legal advice. |
| [HOSTING-PLAN.md](HOSTING-PLAN.md) | Least-exposure host plan, future changes, and access tests. Nothing here is deployed. |
| [EVIDENCE.md](EVIDENCE.md) | Source paths and functions the pages rely on, and the unknowns. |

Open the HTML from this directory. The pages are self-contained: no script, no form, no analytics, no app bundle.

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```

Then open `http://127.0.0.1:8765/`. That local server is only a way to read the drafts. It is not the proposed public host.

## Branch

Cut from `origin/main` at `d306b57` (merged PR 25, already on main). Open PRs 21 and 23 are not included.

## Not done

No DNS, Cloudflare, Access, tunnel, deploy, merge, or push to `main`. No Google API call, no credentials, no migration, no data deletion. `organiser.apidiscoverysolution.uk` is unchanged and stays behind Cloudflare Access.

The draft banner stays until the text is approved. Do not paste the proposed URLs into Google while they 404, and do not paste them while the banner is still the published text, unless Nick decides otherwise.
