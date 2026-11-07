# Hosting plan for the public OAuth pages

Prepare only. Nothing in this file is a change to DNS, Cloudflare, Access, the tunnel, or the app. Every new address below is **PROPOSED**. None of them exist because of this work.

The household app stays at `https://organiser.apidiscoverysolution.uk`, behind Cloudflare Access, for HTML and JSON. That host must not become the OAuth homepage. Google’s rules reject a homepage that is only a login, and they reject a placeholder URL.

## Recommendation

Use a new hostname, on the domain already owned, whose only origin is the three static HTML files.

| Role | URL | Status |
| --- | --- | --- |
| App description (homepage) | `https://organiser-info.apidiscoverysolution.uk/` | PROPOSED |
| Privacy policy | `https://organiser-info.apidiscoverysolution.uk/privacy.html` | PROPOSED |
| Terms of service | `https://organiser-info.apidiscoverysolution.uk/terms.html` | PROPOSED |

`apidiscoverysolution.uk` is the top private domain to register as a Google authorized domain, if it is not already. This draft did not open Search Console or the Cloud console, so that registration is unknown.

The files in this directory are the drafts. The app does not serve `docs/`. `backend/organiser/main.py` mounts the built UI at `/` only when `frontend/dist` exists. These HTML files are not part of that build.

### Why a separate hostname

A public path on `organiser.apidiscoverysolution.uk` would need a Cloudflare Access bypass on the same name as the API and the arrival screen. Access on that host is described as covering HTML and JSON, including `/health`. A bypass that is one path too wide exposes the app. The app’s content-security policy also sets `style-src 'self'`, so these self-contained pages, which use a `<style>` block and no external stylesheet, would not render if they were mounted in the app without a policy change. That would be an application change, and it is not part of this draft.

A path on the apex `apidiscoverysolution.uk` was not chosen. What that name already serves was not inspected. A shared origin can share cookies and a mistaken route with whatever else is there.

A dedicated hostname can have no route to `127.0.0.1:8080`, no database, and no Access application. Public readers get the HTML. They do not get a login wall, and they do not get the API.

### What the public origin must contain

Only the approved HTML. After approval, the published copy drops the draft banner. Until that yes, the banner stays in git.

The origin must not contain:

- the API, or any reverse proxy to port 8080 or to Postgres
- `frontend/dist`, source maps, or other app bundles
- `.env`, OAuth tokens, the Mistral key, or any other secret
- a form, a sign-in button, analytics, or an ad
- directory listing

Suggested response headers, only on this static host:

- `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; img-src data:; script-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`
- `X-Frame-Options: DENY`
- no `Set-Cookie`

`style-src 'unsafe-inline'` is only there because each page carries its own stylesheet. There is no script. Do not copy the app’s header set onto this host without allowing that inline style, and do not loosen the app’s header set so these pages can live inside it.

A request for `/favicon.ico`, `/health`, `/brief/morning`, `/docs`, or `/assets/` should be a 404 from this origin, not a forward to the app.

## Two ways to host it, both waiting on a yes

Both keep the app host unchanged. Neither is set up here.

**Static host with no path to the app (preferred).** Put only the HTML on a static host (for example Cloudflare Pages or an equivalent bucket) and attach the proposed hostname. The app tunnel and the Access application are not edited. A wrong setting on the info host cannot reach port 8080, because that host has no such route. The HTML is public by design and contains no calendar data and no secrets. This does store the public HTML with that static host.

**Separate process on the house, own tunnel route.** Serve only this directory from a process bound to `127.0.0.1` on a port that is not 8080 and not 5432. Add a tunnel public hostname whose only service is that port. Do not attach Access. The failure mode is an ingress rule pointed at 8080 by mistake, which is why the static host above is the smaller exposure. Compose must still not publish Postgres.

A public path on the existing app hostname is the option not recommended. It is not safer than either of the two above.

## Future changes that need a separate yes

None of these are done in this branch.

1. Approve the words, including whether the terms page is published at all. Choose the support address. Remove the draft banner only in the copy that will be published.
2. DNS for `organiser-info` under `apidiscoverysolution.uk`. This is a Cloudflare DNS change. Do not change `organiser`, and do not change `organiser.grok.me`.
3. Stand up the static origin in one of the two ways above. Do not point it at the API.
4. Confirm there is **no** Cloudflare Access application on `organiser-info`. Confirm the existing Access application on `organiser.apidiscoverysolution.uk` is still in place, including `/health` and `/brief/morning`.
5. In Google Search Console, verify the domain with an account that is an Owner or Editor of the Cloud project. Unknown whether this is already done.
6. In the Google Auth Platform, add the authorized domain `apidiscoverysolution.uk` before saving homepage, privacy, or terms URLs. Unknown whether this is already done.
7. After the URLs return the real pages with no login, paste them into the App domain fields. The privacy URL on the homepage and the privacy URL in the console must match, including `https`, the host, and `.html`.
8. The console still needs a user-support email that Google will show on the consent screen. It has to be the logged-in user or a Google Group they manage. Do not invent one. Do not put it on the page until the same address is approved for publication.
9. Branding verification is a console action (Verify branding, then Publish branding within 7 days if it passes). Data-access verification for the scopes is a second step and can ask for more material, including a demo video. This draft does not start either step.
10. An in-app link to the published privacy policy is still missing. Google’s branding page asks for a privacy notice in the product. That would be a later change to the household UI, behind Access, and it is out of scope here.

## Access tests, after a host exists

Run these from a network that is not signed in to Cloudflare Access. Do not weaken Access in order to run them.

Info host, expecting a public page:

```bash
curl -sI https://organiser-info.apidiscoverysolution.uk/
curl -sI https://organiser-info.apidiscoverysolution.uk/privacy.html
curl -sI https://organiser-info.apidiscoverysolution.uk/terms.html
```

Pass: status 200, `content-type` HTML, no `location` pointing at a Cloudflare Access login, no `set-cookie` for an Access session. The homepage body contains `privacy.html` and the proposed privacy URL. The body contains no `GOOGLE_OAUTH`, no client secret, no refresh token, and no Mistral key.

Info host, expecting no app:

```bash
curl -sI https://organiser-info.apidiscoverysolution.uk/health
curl -sI https://organiser-info.apidiscoverysolution.uk/brief/morning
curl -sI https://organiser-info.apidiscoverysolution.uk/docs
curl -sI https://organiser-info.apidiscoverysolution.uk/assets/
```

Pass: 404 from the static origin, not a JSON health body and not the arrival screen.

App host, expecting the access check to be unchanged:

```bash
curl -sI https://organiser.apidiscoverysolution.uk/
curl -sI https://organiser.apidiscoverysolution.uk/health
curl -sI https://organiser.apidiscoverysolution.uk/brief/morning
```

Pass: still an Access challenge. This draft did not call the live host. Do not treat a missing check as something to “fix” by opening the app.

## What Google’s pages require

Fetched 7 November 2026. These drafts do not claim the app will pass.

| Source | Requirement | This draft |
| --- | --- | --- |
| [Manage OAuth App Branding](https://support.google.com/cloud/answer/15549049?hl=en) | External production apps need a homepage, a privacy policy, and a terms link. Homepage on a verified domain you own, describes the app, is not only a login, and links to the same privacy URL as the consent screen. | Pages are written. Domain is not verified here. URLs are PROPOSED and not live. |
| Same page | Privacy policy on the homepage’s domain, discloses how Google user data is accessed, used, stored, and shared, and matches Limited Use. In-product notice. Kept up to date. | Privacy page discloses the reviewed behaviour. In-product notice is not in the app. No certification of Limited Use. |
| Same page | Branding verification is separate from data-access verification. Published branding is required before scope verification. A pass must be published within 7 days. | Not started. |
| [OAuth 2.0 Policies](https://developers.google.com/identity/protocols/oauth2/policies) (modified 5 August 2026) | Production homepage must be public and must link to terms and a privacy policy, on a verified domain. | Same gap: not hosted yet. Terms page is a draft, not counsel. |
| Same policy | Store tokens encrypted at rest. Revoke them when no longer needed, then delete them. Do not send tokens in plaintext. | The app refreshes over an HTTPS URL. It does **not** encrypt the Google refresh token at rest and it has no revoke-and-delete flow. Disclosed as a gap. Not fixed here. |
| Same policy | Personal use (not shared, or under 100 people the operator knows) is not their definition of a production app. Sensitive scopes in a production app need verification. | Nick chose External and is blocked on the branding links. This plan does not rely on a personal-use exception. Whether Google will treat the project as production was not confirmed in the console. |
| [Sensitive scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification) | Reading Calendar events is given as an example of a sensitive scope. Brand verification comes first. The console may ask for more, including a demo. | Scope badges inside the project were not opened. No demo was made. |
| [OAuth scope list](https://developers.google.com/identity/protocols/oauth2/scopes) | Lists both scopes. Sensitive badges are indicated in the Cloud console, not in the fetched table. | The page quotes Google’s scope sentences. It does not invent a console badge. |
| [Calendar scopes](https://developers.google.com/workspace/calendar/api/auth) | `calendar.events.readonly` views events on all calendars. `calendar.calendarlist.readonly` sees the subscribed calendar list. | The privacy page says the consent wording is wider than “today on the primary calendar”. |

Publishing the pages does not submit the app, and a public page does not mean Google will verify the brand or the scopes.

## Approvals still open

- The exact sentences, including the terms page.
- A support address that may be published, and the console user-support email (they should be the same once chosen).
- Whether the consent-screen name stays “Daily Organiser bot”. The pages use that name and say it is not a chat. A misleading name can fail branding review. Renaming it in Google is a console change, not done here.
- Which host (static site, or a house process) and the DNS yes.
- Search Console verification and the authorized domain, if they are not already done.
- Whether to add an in-app privacy link later.
- Whether to encrypt and add a real Google revoke-and-delete path later. That would be a code change, and it is not this branch.
