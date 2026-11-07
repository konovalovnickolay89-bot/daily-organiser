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

`0002_sprint2` adds `shopping_items`, `calendar_subscriptions`, `integration_status`, the `system_state.assistant_enabled` column, and `create_shopping_item` on proposal actions.

`0003_sprint3` adds `commute_shifts` (start, end, and the label `Wembley` only) and `catchup_items.fallback_used`. The boot patch applies the same SQL, so the process starts before the version is moved. After a backup and a yes to deploy, record the revision:

```bash
cd /opt/daily-organiser/backend
PYTHONPATH=. alembic upgrade head
```

Do not stamp `0002` in place of that upgrade. A fresh empty database can also `alembic upgrade head` from an empty `alembic_version`. This repo does not run that command itself.

### Memory needs pgvector (`0004_memory`)

Compose now uses `pgvector/pgvector:pg16`, not `postgres:16-alpine`. The Alpine image has no `vector` type, and this process runs `CREATE EXTENSION vector` on boot before it builds `memory_items`. If the extension is missing, boot fails. discovery-system has to make the database able to load pgvector **before** this revision starts.

- Docker database: change that service's image to `pgvector/pgvector:pg16` (PostgreSQL 16 with pgvector). Do not publish `5432` or any other Postgres port. Evolving Cook still owns `127.0.0.1:5432`.
- System PostgreSQL 16 (no Docker): install the matching package, `postgresql-16-pgvector` on Debian, into **this app's** cluster. Do not install it into Evolving Cook's cluster, and do not change its port. The migration role needs permission to run `CREATE EXTENSION vector` in this database.
- Take a backup first.
- Then record the revision. Do not stamp over it:

```bash
cd /opt/daily-organiser/backend
PYTHONPATH=. alembic upgrade head
```

`0004_memory` creates the extension, `memory_items` (id, kind, text, source, created_at, last_used_at, pinned, embedding `vector(1024)`), an HNSW index, and `agent_proposals.memories_used`. It also allows the proposal actions `remember` and `forget`. The statements are idempotent. The boot patch applies the same SQL, so the process can start before the version is moved, but only after pgvector is installed.

Rollback, after another backup if the memories should be kept:

```bash
cd /opt/daily-organiser/backend
PYTHONPATH=. alembic downgrade 0003_sprint3
```

That deletes remember and forget cards, drops `memory_items` (the memories are gone), drops `memories_used`, restores the previous proposal action check, and runs `DROP EXTENSION vector` in this database only. It does not put the rows back. Restore the backup for that. The image `postgres:16-alpine` can be used again only after this downgrade, because that image cannot read a `vector` column. Staying on `pgvector/pgvector:pg16` after the downgrade is also safe.

No new secret. Embeddings use the existing `MISTRAL_API_KEY` and call `POST /v1/embeddings` on `api.mistral.ai` with model `mistral-embed` (`MISTRAL_EMBED_MODEL` can override the name). If the key is empty or Mistral does not answer, memory still works and retrieval uses words. The postcode and the coordinates are never sent in that call or in the memory slot. `python -m organiser.agent sync` again if the agent instructions should mention the memory slot.

## Ask for discovery-system

Please confirm Cloudflare Access covers `organiser.apidiscoverysolution.uk` for both HTML and JSON, including:

- `/` and the arrival screen
- `/health`
- `/system` and `/system/facts`
- `/tasks`, `/commitments`, `/events`, `/brief`, `/approvals`, `/action-requests`
- `/agent`, `/agent/activity`, `/agent/proposals`, `/catch-up`
- `/memory` and `/memory/export`
- `/commute/shift`
- `/metrics`, `/system/status`, `/alerts`
- `/voice/transcribe` when voice is on. It is 404 while `VOICE_INPUT_ENABLED` is unset
- `/x/status`, `/x/connect`, `/x/callback`, `/x/disconnect`, `/x/watches`, `/x/items`, `/x/poll`
- `/playlist`

Do not change Cloudflare, tunnels, or DNS from this repo. Access is the only login.

### Environment names for this deploy

Add nothing secret to git. In the existing house file:

| Name | This sprint |
| --- | --- |
| `ENABLE_DOCS`, `DOCS_BEHIND_ACCESS` | Leave both unset or `false`. Docs come on only when both are true, and only behind Access |
| `MISTRAL_API_KEY`, `MISTRAL_AGENT_ID` | Already in use, or empty to keep the assistant off. Settings can also switch it off without deleting the keys. The same key is used for embeddings. Empty keeps memory on words only |
| `MISTRAL_EMBED_MODEL` | Optional. Default `mistral-embed` (1024 dimensions). Do not point this at a different size without a migration |
| `HOUSE_LAT` and `HOUSE_LON`, or `HOUSE_POSTCODE` | Weather. Do not commit or log the value. Coordinates win when both are set. A postcode is resolved through postcodes.io and not stored |
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REFRESH_TOKEN` | Read-only diary. Scopes: `calendar.events.readonly` and `calendar.calendarlist.readonly`. No write scope |
| `GOOGLE_CALENDAR_IDS` | Optional. Blank means `primary` until Settings stores names |
| `TFL_APP_KEY` | Journey check, and `GET /tfl/status` for line status with no shift. Empty leaves the brief line “Journey check is not connected.” and line status “TfL is not configured.” Do not commit or log the key. No new variable |
| `BANTO_COMMUTE_TOKEN` | Bearer for `POST /commute/shift`. Empty leaves the push unwired. The body is only `start`, `end`, and `location_label`, and the only label stored is `Wembley` |
| `WEBHOOK_SECRET_BANTO` | HMAC secret for `POST /hooks/banto`. Leave empty to keep the webhook closed (503). The signature is hex HMAC-SHA256 of `{unix timestamp}.{raw body}`, headers `X-Organiser-Timestamp` and `X-Organiser-Signature`. The timestamp must be within five minutes, and each signature is accepted once in that window. The only event is `commute`, and it uses the same shift check. A rejected body is not stored |
| `WEBHOOK_SECRET_BANTO_X` | HMAC secret for `POST /hooks/banto_x`. Leave empty to keep that door closed (503). Events: `x.bookmark`, `x.watch_match`, `x.draft`. Same signature rules as Bantō. Refused while `X_ENABLED` is off. A body outside the house is not stored |
| `X_ENABLED` | Leave unset or `false` until Nick wants X. `true` turns on connect, the poll, cards, and confirmed posts |
| `X_CLIENT_ID`, `X_CLIENT_SECRET` | From Nick's own X app. See the setup steps below. Do not commit or log the secret |
| `X_REDIRECT_URI` | `https://organiser.apidiscoverysolution.uk/x/callback`. It must match the app exactly |
| `X_TOKEN_KEY` | Fernet key. Refresh and access tokens are sealed with it before they are stored. Generate it on the box and do not commit it |
| `X_POLL_MINUTES` | Optional. Default 30. Bookmarks and the watch list are not read more often than this, and a 429 backs off |
| `PLAYLIST_SOURCE` | `hearthis` for the Chlorophil line. Empty hides it |
| `HEARTHIS_PROFILE` | Optional. Default `chlorophil` |
| `SHOW_PLAYLIST` | Leave unset once a source is set (the line comes on). `false` hides it. The tap opens hearthis in a new tab. Nothing is streamed |
| `RATE_FEED_PER_MINUTE`, `RATE_INGEST_PER_MINUTE`, `RATE_COMMUTE_PER_HOUR` | Optional. Defaults are 6 a minute, 30 a minute, and 12 an hour. Each limit is for this process and resets on restart |
| `VOICE_INPUT_ENABLED` | Leave unset or `false`. `true` shows voice on Smart Add only. Stop and transcribe sends one clip to Mistral. Cancel recording does not upload. Recordings are not written to disk, the database, or the logs. Text waits in the box until Add |
| `MISTRAL_TRANSCRIBE_MODEL` | Optional. Default `voxtral-mini-transcribe-3`. Used only when voice is on, with the existing `MISTRAL_API_KEY`. If this is set to `voxtral-mini`, that value is what is sent |

Logs are one JSON object per line on stdout: time, level, logger, message, and for requests the method, path, status, and duration. No body, query string, postcode, coordinate, token, or secret. A context line is the schema version and the counts per section, never the titles. `/health` adds `version` (currently `0.4.0`) beside `status` and `database`. `/metrics` is Prometheus text for the same process.

Rebuild the UI (`npm ci && npm run build` in `frontend/`) before restarting the process. The app boots without the migration because of the boot patch, once pgvector is installed. Still run `alembic upgrade head` after a backup so `0005_sprint6` is recorded. Do not stamp over it. Cloudflare Access is still the only login for people. The webhook is a separate signed door and does not add an account.

Outbound HTTPS to allow when those values are set: `api.open-meteo.com`, `api.postcodes.io` (only if a postcode is used), `api.tfl.gov.uk` (only if `TFL_APP_KEY` is set), `oauth2.googleapis.com`, `www.googleapis.com`, `api.x.com` (only if `X_ENABLED` is on), and `api-v2.hearthis.at` (only if `PLAYLIST_SOURCE=hearthis`). The browser, not the process, opens `x.com` to connect and `hearthis.at` for a track, and loads thumbs from `img.hearthis.at`. No bodies, tokens, coordinates, or postcodes in logs.

The app boots without the migration because of the boot patch, once pgvector is installed. Still run `alembic upgrade head` after a backup so `0006_sprint7` is recorded. Do not stamp over it.

## Sprint 6, when discovery-system deploys it

Do this after a backup. This repo does not install the unit, and it does not change Cloudflare, tunnels, or DNS.

1. `cd /opt/daily-organiser/backend && PYTHONPATH=. alembic upgrade head` so `0005_sprint6` is recorded. That adds `alert_dismissals`. Do not stamp over it. The process also creates the table on boot, so it starts before the version is moved.
2. Rebuild the UI (`npm ci && npm run build` in `frontend/`) and restart the process. `/health` reports version `0.3.0`.
3. Leave `VOICE_INPUT_ENABLED` unset until Nick wants the mic. When it is set, allow the existing outbound call to `api.mistral.ai`. No new secret. `MISTRAL_TRANSCRIBE_MODEL` defaults to `voxtral-mini-transcribe-3`. Leave it unset, or set that id. Do not set `voxtral-mini`.
4. Run `python -m organiser.agent sync` if the agent instructions should mention that a personal hotel stay is household life and Hilton, a guest, a colleague, an employer, or a work system is not.
5. Cloudflare Access should cover `/metrics`, `/system/status`, `/alerts`, and `/voice/transcribe`. `/metrics` is counts and timings. Alert cards stay in the app: nothing is emailed or sent. A Mistral failure (3 or more in 15 minutes), a quiet activity poll (over 2 hours, Monday to Friday, 06:00–21:59 London), and a database error each show one card that can be dismissed.

Rollback of the table: `alembic downgrade 0004_memory`. That drops `alert_dismissals`. The cards are computed, so they return on their own. Voice stays off when the flag is removed. No audio was stored, so there is nothing to delete.

## X app, for Nick

This uses Nick's own app on the X developer portal. The house does not share an app with anyone else. Leave `X_ENABLED` unset until the values below are in the house file.

1. Create a project and an app in the X developer portal, on Nick's account.
2. Set user authentication to OAuth 2.0. The app type is a confidential web app. Do not use OAuth 1.0a.
3. Callback URL, exactly: `https://organiser.apidiscoverysolution.uk/x/callback`
4. Scopes: `tweet.read`, `users.read`, `bookmark.read`, `tweet.write`, `offline.access`.
5. Copy the client id and client secret into the house file as `X_CLIENT_ID` and `X_CLIENT_SECRET`. Set `X_REDIRECT_URI` to that same callback URL.
6. On the box, generate a Fernet key and put it in `X_TOKEN_KEY`. Do not commit it and do not paste it into chat:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

7. Set `X_ENABLED=true` and restart. In Settings, tap Connect. X asks Nick to allow those scopes. Disconnect revokes the refresh token and deletes the sealed copy.
8. The watch list is accounts or keywords, edited in Settings. Bookmarks and that list are read about every 30 minutes (`X_POLL_MINUTES`). A card is Apply or Not now. Apply keeps the line in the log. It does not post.
9. A draft is posted only when Nick taps Post and then confirms. Drafts expire after 7 days. Each attempt is an audit row. Hilton, a guest, a colleague, an employer, or a work system is refused and not stored.
10. A relay can still post `x.bookmark`, `x.watch_match`, or `x.draft` to `POST /hooks/banto_x` with `WEBHOOK_SECRET_BANTO_X`. The same pipeline, the same refusal. Leave the secret empty until that relay exists.

`python -m organiser.agent sync` again if the agent should offer `propose_draft`. That function only proposes. It does not post.

## Sprint 7, when discovery-system deploys it

Do this after a backup. This repo does not install the unit, and it does not change Cloudflare, tunnels, or DNS.

1. Allow outbound HTTPS to `api.x.com` if X will be on, and to `api-v2.hearthis.at` if the playlist line will be on. The browser also needs `img.hearthis.at` for the thumb. Do not open a new public port.
2. `cd /opt/daily-organiser/backend && PYTHONPATH=. alembic upgrade head` so `0006_sprint7` is recorded. That adds `x_connection`, `x_oauth_pending`, `x_watches`, `x_items`, `x_cursors`, `x_meter`, and `x_post_audit`. Tokens in `x_connection` are ciphertext. Do not stamp over it. The process also creates the tables on boot.
3. Put the X and playlist names in the existing house file. Leave `X_ENABLED` unset until the app setup above is done. `PLAYLIST_SOURCE=hearthis` and `HEARTHIS_PROFILE=chlorophil` show the line. `SHOW_PLAYLIST=false` hides it. `SHOW_PLAYLIST_STUB` is no longer read.
4. Rebuild the UI (`npm ci && npm run build` in `frontend/`) and restart the process. `/health` reports version `0.4.0`. Reinstall `backend/requirements.txt` so `cryptography` is present.
5. Cloudflare Access should cover `/x/status`, `/x/connect`, `/x/callback`, `/x/disconnect`, `/x/watches`, `/x/items`, `/x/poll`, and `/playlist`.

Rollback of the tables, after a backup: `alembic downgrade 0005_sprint6`. That drops the X rows, including sealed tokens and the post audit. A post that already went to X stays on X. Set `X_ENABLED` empty before the downgrade so a restart does not call X. The playlist line hides when `PLAYLIST_SOURCE` is empty.

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
