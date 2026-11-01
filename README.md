# Daily Organiser

Home operations for Nick: a household log, a morning brief, and a quiet arrival screen. Tasks, commitments, and approvals carry an owner and a status. Events are the memory of what was recorded. The presence bar can pause the house.

This is not a chat and not a sidekick. “Welcome home” is the arrival line. Nothing here speaks, listens, or greets in a conversation.

Approvals stop at the log. Observe, advise, and prepare update a status. Execute can be approved and still does nothing outside this database: no message, no purchase, no booking.

Home only. No work systems, and no Hilton or guest data.

The house Debian box will run this later as PostgreSQL plus one process. `organiser.grok.me` is not set up here. See `DEPLOY.md`.

## Layout

```
backend/organiser/     FastAPI service (Postgres, brief, approvals, pause)
backend/tests/         Schema and API tests
frontend/src/api/      The only place the UI calls the API
frontend/src/arrival/  Module registry for the arrival screen
frontend/src/modules/  Presence bar, brief, approvals, today, quiet suggestion
docker-compose.yml     Internal Postgres; API and UI on 127.0.0.1:8080 only
DEPLOY.md              systemd sketch for later; nothing is installed
```

```
browser  →  arrival UI
               │  REST, same origin
               ▼
            FastAPI  →  PostgreSQL
            tasks, commitments, events, action_requests, system_state
```

A later screen is a module in `frontend/src/arrival/modules.js` plus a function in `frontend/src/api/`. The shell already has slots: `primary`, `secondary`, and `corner`.

## Run the whole stack

Docker Compose starts Postgres, the API, and the arrival screen. Postgres has no host port. It is reachable only as the hostname `db` on the compose network. Evolving Cook already listens on `127.0.0.1:5432` on the house box, so this file does not publish `5432` or any other Postgres port.

The only published port is the API on the host loopback. Inside the container the process listens on `0.0.0.0:8080` so Docker can forward that one address. It is not published on the LAN. The same process serves the built UI.

```bash
docker compose up --build
```

Open http://127.0.0.1:8080. Interactive API docs are on that same origin at http://127.0.0.1:8080/docs.

The database password in Compose is a local default (`organiser`). Do not reuse it on the house box.

Stop it with Ctrl-C. `docker compose down -v` drops the compose database. With `SEED_ON_START=true`, the next start fills the log again only when there are no tasks.

## Run it while editing

Leave Postgres inside Compose (`docker compose up -d db`). Do not add a host port for it.

The API container can be started on the loopback with the source mounted, still talking to hostname `db`:

```bash
docker compose run --rm --service-ports \
  -v "$PWD/backend/organiser:/app/organiser" \
  api
```

That publishes `127.0.0.1:8080` only when the `api` service is not already running. Stop the service first if the port is taken.

For the Vite dev server, with the API already on `127.0.0.1:8080`:

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies the API, so leave `VITE_API_BASE_URL` empty.

A host virtualenv is fine on a machine that is not the house box. Set `DATABASE_URL` yourself. On the house box, do not point it at `127.0.0.1:5432`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
PYTHONPATH=backend python -m organiser
```

That listens on `127.0.0.1:8080` (`HOST` and `PORT` in `.env.example`).

## One process, the shape of the house box

Build the UI, then let FastAPI serve `frontend/dist` and the API together, bound to the loopback.

```bash
cd frontend && npm ci && npm run build && cd ..
PYTHONPATH=backend python -m organiser
```

Open http://127.0.0.1:8080. `DEPLOY.md` is the later systemd note. This repo does not install it, and it does not take Evolving Cook’s Postgres port.

## Tests

Tests use PostgreSQL, never SQLite. They create `organiser_test` when the role is allowed to, and they do not read the demo database. The compose test profile uses hostname `db` and publishes nothing.

```bash
docker compose --profile test run --rm tests
```

On a machine that is not the house box, a private database can be named with `TEST_DATABASE_URL`. Do not use Evolving Cook’s `127.0.0.1:5432`.

```bash
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
TEST_DATABASE_URL=postgresql+psycopg://organiser:organiser@<host>/<db> pytest
```

`SEED_ON_START` is forced off inside the tests.

## API

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/health` | Process and database are up |
| GET, POST | `/tasks` | List and create. Filters: `status`, `priority`, `owner`, `due_on`, `scope=today` |
| GET, PATCH, DELETE | `/tasks/{id}` | One task |
| GET, POST | `/commitments` | List and create. Filter: `status`, `owner` |
| GET, PATCH, DELETE | `/commitments/{id}` | One commitment |
| GET, POST | `/events` | Operational log. Filter: `kind`, `owner` |
| GET, PATCH, DELETE | `/events/{id}` | One event |
| GET, POST | `/action-requests` | List and create. Filter: `status`, `mode`, `owner` |
| GET, PATCH, DELETE | `/action-requests/{id}` | One request. `effect_applied` cannot be set |
| GET | `/brief/morning` | Tasks due today or overdue, open commitments, and placeholder appointments, shopping, and weather |
| GET | `/approvals` | Pending requests. `status=all` lists every decision |
| POST | `/approvals/{id}/approve` | Status becomes approved. Nothing outside the log changes |
| POST | `/approvals/{id}/skip` | Status becomes skipped |
| GET | `/system` | Pause flag, activity, and status line for the presence bar |
| POST | `/system/pause` | Pause. Repeating it does not write a second log line |
| POST | `/system/unpause` | Resume |

Task status is `todo`, `doing`, or `done`. Priority is `low`, `medium`, or `high`. Commitment status is `open`, `kept`, or `dropped`. An action mode is `observe`, `advise`, `prepare`, or `execute`. An action status is `pending`, `approved`, or `skipped`. Owner defaults to `Nick`.

`scope=today` is the house date in `HOUSE_TIMEZONE` (default `Europe/London`): not done, due today or earlier. The morning brief also includes open tasks with no date. A task due later stays on the full list only.

Approve and skip return `effect.applied: false` and a short summary. The `action_requests.effect_applied` column is constrained to false.

## Arrival screen

One home screen:

1. Centred presence bar: “Welcome home”, the system status, and Pause / Resume.
2. Left: morning brief. Tasks and open commitments come from the API. Appointments, shopping, and weather are labelled as not connected.
3. Right: pending approvals, then a short Today list.
4. Corner: “A playlist is ready, when you want it.” It is text only. It does not play anything and it does not control the house.

Pausing changes the presence bar and writes one system event. It does not send or prepare anything. Approving while paused still only updates the log.

## Demo rows

When the task table is empty and `SEED_ON_START` is true, the API inserts a small household: bins, plants, a hallway bulb, a boiler reminder that is not booked, two open commitments, a kept one, and four pending decisions including an execute request that cannot send a message.

## What this does not do

No merge to `main`, no deploy, no Cloudflare, no voice, no live weather, no playlist service, and no shopping that buys anything.
