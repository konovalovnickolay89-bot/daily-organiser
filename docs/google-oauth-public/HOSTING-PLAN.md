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

The three HTML files are the publication text, including the approved support email. They are in git only. The app does not serve `docs/`. `backend/organiser/main.py` mounts the built UI at `/` only when `frontend/dist` exists. These HTML files are not part of that build. The hostname is still PROPOSED: it does not resolve because of this work.

### Why a separate hostname

A public path on `organiser.apidiscoverysolution.uk` would need a Cloudflare Access bypass on the same name as the API and the arrival screen. Access on that host is described as covering HTML and JSON, including `/health`. A bypass that is one path too wide exposes the app. The app’s content-security policy also sets `style-src 'self'`, so these self-contained pages, which use a `<style>` block and no external stylesheet, would not render if they were mounted in the app without a policy change. That would be an application change, and it is not part of this draft.

A path on the apex `apidiscoverysolution.uk` was not chosen. What that name already serves was not inspected. A shared origin can share cookies and a mistaken route with whatever else is there.

A dedicated hostname can have no route to `127.0.0.1:8080`, no database, and no Access application. Public readers get the HTML. They do not get a login wall, and they do not get the API.

### What the public origin must contain

Only the three publication HTML files: `index.html`, `privacy.html`, and `terms.html`. Do not upload this markdown, the evidence notes, or the rest of the repository. The HTML no longer carries a draft banner. The support email on those pages is `mykolakonovalov@gmail.com`, which is approved for that public contact and for the consent-screen user-support field. That approval does not create this host.

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

## One host, and it is not set up

Cloudflare Pages, with a project that contains only those three HTML files, on the hostname `organiser-info.apidiscoverysolution.uk`.

That is the lowest-exposure option because the pages have no tunnel, no process, and no route that can be pointed at `127.0.0.1:8080`. discovery-system already operates Cloudflare for `apidiscoverysolution.uk`. This plan does not add a second DNS provider, a house port, or an Access bypass. It does not state a price. Whether the existing Cloudflare account can hold a static project is for discovery-system to know. No paid add-on is requested.

A house process behind a new tunnel route can be aimed at the API by a bad ingress rule. A public path on `organiser.apidiscoverysolution.uk` needs an Access bypass. Neither is the recommendation.

### Resources discovery-system would create, after a separate yes

None of this is created here.

| Resource | What it is |
| --- | --- |
| Pages project | A new static project. Suggested name `organiser-info`. Contents are only `index.html`, `privacy.html`, and `terms.html`. Not the git repository. |
| DNS record | `organiser-info.apidiscoverysolution.uk` pointed at that Pages project. Leave the `organiser` record alone. Leave `organiser.grok.me` alone. |
| TLS | The certificate Cloudflare already issues for names in this zone. No separate certificate product is requested. |
| Access | No Access application on `organiser-info`. The Access application on `organiser.apidiscoverysolution.uk` stays, including `/health` and `/brief/morning`. |
| Headers | The static-host headers listed above. No cookies. |

### Approval gate for discovery-system

The support-email approval does not authorize discovery-system to do this. A later yes has to name this Pages project, this hostname, and the three files, and it has to say the app tunnel and the Access application are untouched. Until that yes, do not create the project or the DNS record.

## Other yeses, separate from the email

The email `mykolakonovalov@gmail.com` is approved as the public support contact and as the value for the consent-screen user-support field. It is not approval for the rows below.

1. discovery-system creates the Pages project and the DNS record, as above.
2. Run the access tests in the next section. They are not run here.
3. In Google Search Console, verify `apidiscoverysolution.uk` with an account that is an Owner or Editor of the Cloud project. Unknown whether this is already done.
4. In the Google Auth Platform, add the authorized domain `apidiscoverysolution.uk` before saving the homepage, privacy, or terms URLs. Unknown whether this is already done.
5. After the tests pass, paste the three URLs into the App domain fields. The privacy URL on the homepage and the privacy URL in the console must match, including `https`, the host, and `.html`. Pasting and clicking Verify branding or Publish branding is a Google authorization. It is not given here.
6. Branding verification can then be started in the console (Verify branding, then Publish branding within 7 days if it passes). Data-access verification for the scopes is a second step and can ask for more, including a demo. Neither is started here.
7. The in-app privacy link in `IN_APP_NOTICE.md` waits until the privacy URL returns 200 with no Access login. It is not in the app.

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
| [OAuth 2.0 Policies](https://developers.google.com/identity/protocols/oauth2/policies) (modified 5 August 2026) | Production homepage must be public and must link to terms and a privacy policy, on a verified domain. | Pages link to each other. Not hosted yet. Terms set no court, liability cap, or warranty. |
| Same policy | Store tokens encrypted at rest. Revoke them when no longer needed, then delete them. Do not send tokens in plaintext. | The app refreshes over an HTTPS URL. It does **not** encrypt the Google refresh token at rest and it has no revoke-and-delete flow. Disclosed as a gap. Not fixed here. |
| Same policy | Personal use (not shared, or under 100 people the operator knows) is not their definition of a production app. Sensitive scopes in a production app need verification. | Nick chose External and is blocked on the branding links. This plan does not rely on a personal-use exception. Whether Google will treat the project as production was not confirmed in the console. |
| [Sensitive scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification) | Reading Calendar events is given as an example of a sensitive scope. Brand verification comes first. The console may ask for more, including a demo. | Scope badges inside the project were not opened. No demo was made. |
| [OAuth scope list](https://developers.google.com/identity/protocols/oauth2/scopes) | Lists both scopes. Sensitive badges are indicated in the Cloud console, not in the fetched table. | The page quotes Google’s scope sentences. It does not invent a console badge. |
| [Calendar scopes](https://developers.google.com/workspace/calendar/api/auth) | `calendar.events.readonly` views events on all calendars. `calendar.calendarlist.readonly` sees the subscribed calendar list. | The privacy page says the consent wording is wider than “today on the primary calendar”. |

Publishing the pages does not submit the app, and a public page does not mean Google will verify the brand or the scopes.

## Approvals

Approved: `mykolakonovalov@gmail.com` as the public support email for Daily Organiser bot, on these pages and as the consent-screen user-support value. The consent-screen name stays Daily Organiser bot.

Not approved by that email: the Pages project, the DNS record, Access changes, pasting URLs into Google, Verify branding, Publish branding, scope verification, token minting, or the in-app link. Encrypting the Google refresh token and adding a revoke-and-delete path would be a later code change. It is not this branch.
