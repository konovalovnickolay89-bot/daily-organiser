# Security checklist

Reviewed for this sprint. The house hostname stays behind Cloudflare Access, which is the only login for a person. This app has no accounts. Access is ops-managed: this repo does not change Cloudflare, tunnels, or DNS.

## Secrets stay in the environment

`MISTRAL_API_KEY`, the Google OAuth values, `HOUSE_LAT`, `HOUSE_LON`, `HOUSE_POSTCODE`, `TFL_APP_KEY`, `BANTO_COMMUTE_TOKEN`, `WEBHOOK_SECRET_BANTO`, and `WEBHOOK_SECRET_BANTO_X` are read from the environment. They are `SecretStr` fields, so a settings dump does not print them. They are not in git, fixtures, or logs. `.env.example` lists the names with empty placeholders. The Compose database password is a local default only.

`WEBHOOK_SECRET_BANTO_X` is reserved for a later X relay. That source is not registered, so the value does nothing until a later change adds it.

## CORS

`CORS_ORIGINS` defaults to the local dev origins (`localhost` and `127.0.0.1` on ports 5173 and 8080). There is no `*` origin. The house UI is same-origin, so the browser does not need a cross-origin allowance there. Leave the list as the local origins unless a later host truly serves the UI from another origin.

## Security headers

Every response, including `/health` and the built UI, sets:

| Header | Value |
| --- | --- |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `no-referrer` |
| `X-Frame-Options` | `DENY` |
| `Content-Security-Policy` | `default-src 'self'`; images `self` and `data:`; style, font, script, and connect `self`; `frame-ancestors 'none'`; `base-uri 'self'`; `form-action 'self'` |
| `Permissions-Policy` | camera, microphone, geolocation, and payment disabled |
| `Cross-Origin-Opener-Policy` | `same-origin` |
| `X-Permitted-Cross-Domain-Policies` | `none` |

The theme boot script is `/theme-boot.js`, so the policy does not need `unsafe-inline` for scripts. `/docs` stays off on the house. Swagger would not load under this policy, which is acceptable while docs are disabled.

## pip and npm audit

`pip-audit` against `backend/requirements.txt` on this run reported no known vulnerabilities (FastAPI 0.162.0, uvicorn 0.54.0, SQLAlchemy 2.1.8, psycopg 3.3.8, pydantic-settings 2.16.2, httpx 0.28.1, alembic 1.20.1, and their dependencies).

`npm audit` in `frontend/` after moving PostCSS to 8.5.32: no critical, high, or low findings. Seven moderate findings remain, all in the lint toolchain (`minimatch` through `typescript-eslint`). They are not in the arrival screen bundle. The suggested npm fix downgrades `typescript-eslint` and was not applied.

## Home scope on inbound routes

A hotel, a guest, a colleague, or an employer is refused with `422` and `Not for the house log.` on:

- `POST` and `PATCH` `/tasks`, `/commitments`, `/events`, `/action-requests`
- `POST` `/shopping` and calendar names
- `POST` `/agent/feed`, `POST` `/agent/proposals`, and proposal apply for a shop name
- `POST` `/memory`, remember and forget in the box, and Apply on those cards
- `POST` `/commute/shift` and the `banto` commute webhook

The diary drops titles outside the house before they reach the brief. The context builder drops the same titles before they are handed to Smart Add. Memory refuses the same texts, and also work email, a workplace, or payroll. Embeddings and the memory slot are redacted first: a UK postcode, a coordinate, and the configured house location are not sent. `GET /memory` and `GET /memory/export` do not call Mistral. The export has no embedding.

## No location in logs

Log lines are JSON. A request records method, path, status, and duration. It does not record the body, the query string, or headers. A scrubber redacts `key`/`secret`/`token`/`password` assignments, UK postcodes, and coordinates with four or more decimal places. httpx and httpcore are kept at warning so a URL is not written at info. Weather and diary failures log a fixed sentence, not the exception, because the exception can contain the request URL.

## Cloudflare Access is the only login

People sign in with Cloudflare Access on `organiser.apidiscoverysolution.uk`. This process does not check Access and does not grow a user table. Discovery-system owns the Access application, for HTML and for JSON, including `/health`, `/hooks`, and `/commute`.

`POST /hooks/{source}` is the machine door. It is not a second login. The body is signed with HMAC-SHA256 over `{timestamp}.{raw body}` using `WEBHOOK_SECRET_BANTO`. The timestamp header has to fall within five minutes, and a signature is kept only long enough to refuse a replay. The cache stores the signature, not the body. A bad signature, an unknown source, an unknown event, or a shift that fails the commute check writes no row.

## Webhook shape

```
POST /hooks/banto
X-Organiser-Timestamp: <unix seconds>
X-Organiser-Signature: <hex hmac>

{"event":"commute","start":"...","end":"...","location_label":"Wembley"}
```

`POST /commute/shift` takes the same three shift fields without the signature. It is for the house, behind Access, and uses the same validator.
