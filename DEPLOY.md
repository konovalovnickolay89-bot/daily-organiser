# Later deploy note

This is a sketch for the house Debian box. Nothing in this file is installed by the repo. An agent must not add a unit under `/etc`, create a host user, or change firewall, packages, Cloudflare, or DNS.

Discovery-system looks after that box. The public hostname is `organiser.apidiscoverysolution.uk`. Cloudflare Access is the only login. This app has no accounts. `organiser.grok.me` is not this service. Do not point a tunnel or a DNS change at it from this repo.

## One machine

The house box runs:

- PostgreSQL for this app, not Evolving Cook’s server
- one FastAPI process on `127.0.0.1:8080`, which also serves the built arrival screen from `frontend/dist`

Evolving Cook already listens on `127.0.0.1:5432`. This app must not bind a Postgres port there, and `docker-compose.yml` does not publish one. A later database for Daily Organiser has to be a different cluster (a socket or another address). `DATABASE_URL` must not be Evolving Cook’s database.

There is no second hostname for the UI. Do not invent an IP. Local development uses Compose: Postgres stays on the internal network, and the only published port is `127.0.0.1:8080`. The house install does not need the Vite dev server.

## Shape of a future install

A later change, owned by discovery-system, can:

1. Put the repo on the box, for example `/opt/daily-organiser`.
2. Provide a PostgreSQL database that is not Evolving Cook’s `127.0.0.1:5432`. Keep the password out of git.
3. Create a virtualenv and install `backend/requirements.txt`.
4. On that same box, build the UI (`npm ci && npm run build` in `frontend/`) with `VITE_API_BASE_URL` left empty, so the browser calls the API on the same origin.
5. Keep secrets in the house environment file this app already uses. Older notes named `/etc/daily-organiser.env`. Do not create a second file. Start from `.env.example`, but put real values only in that existing house file. Set `DATABASE_URL` to this app’s own database, `HOST=127.0.0.1`, `PORT=8080`, `ENABLE_DOCS=false`, and `SEED_ON_START=false` once real household rows exist.
6. Run one process as a dedicated user, after PostgreSQL is up.

Example unit discovery-system might install later. It is not part of this repo and it is not enabled here. `EnvironmentFile` must be the house file that already exists, not a new path invented here:

```ini
[Unit]
Description=Daily Organiser
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=organiser
WorkingDirectory=/opt/daily-organiser/backend
Environment=PYTHONPATH=/opt/daily-organiser/backend
EnvironmentFile=<the house environment file discovery-system already uses>
ExecStart=/opt/daily-organiser/.venv/bin/python -m organiser
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

`python -m organiser` reads `HOST` and `PORT` from the environment (default `127.0.0.1:8080`). The static files are found from `frontend/dist` next to `backend/`, or from `/app/frontend/dist` in the API image. Build them before starting the unit. Until `frontend/dist/index.html` exists, `/` is a short JSON pointer and `/health` still works.

`/docs`, `/redoc`, and `/openapi.json` answer 404 unless `ENABLE_DOCS=true` and `DOCS_BEHIND_ACCESS=true`. Leave both false on the house. The second flag means those paths are already behind Cloudflare Access. This app does not check Access.

`SEED_ON_START=true` fills an empty task list with household demo rows. Turn it off after real tasks exist, or the next empty database will be filled again.

## Schema

The process still creates tables with `create_all` and the small `ensure_*` patches, so a database from before this revision still boots. Alembic `0001_baseline` was stamped, not upgraded, on the house database.

`0002_sprint2` adds `shopping_items`, `calendar_subscriptions`, `integration_status`, the `system_state.assistant_enabled` column, and `create_shopping_item` on proposal actions. The boot patch applies the same SQL, so the process starts before the version is moved. After a backup and a yes to deploy, record the revision:

```bash
cd /opt/daily-organiser/backend
PYTHONPATH=. alembic upgrade head
```

Do not stamp `0002` in place of that upgrade. A fresh empty database can also `alembic upgrade head` from an empty `alembic_version`. This repo does not run that command itself.

## Ask for discovery-system

Please confirm Cloudflare Access covers `organiser.apidiscoverysolution.uk` for both HTML and JSON, including:

- `/` and the arrival screen
- `/health`
- `/system` and `/system/facts`
- `/tasks`, `/commitments`, `/events`, `/brief`, `/approvals`, `/action-requests`
- `/agent`, `/agent/activity`, `/agent/proposals`, `/catch-up`

Do not change Cloudflare, tunnels, or DNS from this repo. Access is the only login.

### Environment names for this deploy

Add nothing secret to git. In the existing house file:

| Name | This sprint |
| --- | --- |
| `ENABLE_DOCS`, `DOCS_BEHIND_ACCESS` | Leave both unset or `false`. Docs come on only when both are true, and only behind Access |
| `MISTRAL_API_KEY`, `MISTRAL_AGENT_ID` | Already in use, or empty to keep the assistant off. Settings can also switch it off without deleting the keys |
| `HOUSE_LAT` and `HOUSE_LON`, or `HOUSE_POSTCODE` | Weather. Do not commit or log the value. Coordinates win when both are set. A postcode is resolved through postcodes.io and not stored |
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REFRESH_TOKEN` | Read-only diary. Scopes: `calendar.events.readonly` and `calendar.calendarlist.readonly`. No write scope |
| `GOOGLE_CALENDAR_IDS` | Optional. Blank means `primary` until Settings stores names |
| `TFL_APP_KEY`, `BANTO_COMMUTE_TOKEN` | Leave empty. Not connected. `Wembley` means Wembley Park, origin home |
| `WEBHOOK_SECRET_BANTO` | HMAC secret for `POST /hooks/banto`. Leave empty to keep the webhook closed (503). The signature is hex HMAC-SHA256 of `{unix timestamp}.{raw body}`, headers `X-Organiser-Timestamp` and `X-Organiser-Signature`. The timestamp must be within five minutes, and each signature is accepted once in that window. The only event is `commute`: `start`, `end`, and `location_label`. A rejected body is not stored |
| `WEBHOOK_SECRET_BANTO_X` | Reserve the name for the X relay. Do not set it until that source is registered. It does nothing now |
| `SHOW_PLAYLIST_STUB` | Leave unset or `false`. The playlist line stays hidden. `true` shows the text only; nothing plays |

Logs are one JSON object per line on stdout: time, level, logger, message, and for requests the method, path, status, and duration. No body, query string, postcode, coordinate, or secret. `/health` adds `version` (currently `0.2.0`) beside `status` and `database`.

No new migration. Rebuild the UI (`npm ci && npm run build` in `frontend/`) before restarting the process, because the arrival screen moved to TypeScript. Cloudflare Access is still the only login for people. The webhook is a separate signed door and does not add an account.

Outbound HTTPS to allow when those values are set: `api.open-meteo.com`, `api.postcodes.io` (only if a postcode is used), `oauth2.googleapis.com`, `www.googleapis.com`. No bodies, tokens, coordinates, or postcodes in logs.

The app boots without the migration because of the boot patch. Still run `alembic upgrade head` after a backup so `0002_sprint2` is recorded. Do not stamp over it.

## Mistral assistant, later

The assistant ships off. It stays off on the box until discovery-system, with Nick's yes:

1. Confirms Cloudflare Access guards the public hostname. The app has no login. Without Access, anyone with the link could spend the key's credit and read the log through the assistant.
2. Adds `MISTRAL_API_KEY` and `MISTRAL_AGENT_ID` to the existing house environment file. Nick creates the agent with `python -m organiser.agent sync` (see `docs/mistral-agent.md`).
3. Allows outbound HTTPS from the box to `api.mistral.ai`.
4. Reinstalls `backend/requirements.txt` in the virtualenv. `httpx` and `alembic` are runtime dependencies.

Nothing is scheduled on the host. The display at home asks for the morning review and other reviews when the rules say one is due.

## Cloudflare

Access on the hostname above is the login. Do not add or edit a cloudflared ingress, a tunnel, or a DNS record in an application change. `organiser.grok.me` is not this service.

## Data scope

Personal household records only. Do not point this service at work systems or at Hilton or guest data. Approvals record a decision. They do not send, buy, or book. The diary, when a later sprint connects it, is a read-only list of personal appointments. It is not a calendar app.
