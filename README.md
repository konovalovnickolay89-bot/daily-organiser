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
docker-compose.yml     Local Postgres, API, and UI
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

Docker Compose starts Postgres, the API (with demo rows), and the arrival screen.

```bash
docker compose up --build
```

Open http://localhost:8080. The API is also at http://localhost:8000, and the docs are at http://localhost:8000/docs.

The database password in Compose is a local default (`organiser`). Do not reuse it on the house box.

Stop it with Ctrl-C. `docker compose down -v` drops the local database. With `SEED_ON_START=true`, the next start fills the log again only when there are no tasks.

If port 5432 is already taken by another Postgres, stop that one first or change the host port in `docker-compose.yml` and `DATABASE_URL`.

## Run it while editing

Terminal A, Postgres only:

```bash
docker compose up db
```

Or use a Postgres you already have, and create the role and database:

```bash
createuser --pwprompt organiser
createdb --owner=organiser organiser
```

The URL in `.env.example` matches the Compose defaults. Copy it if you want the file; the environment variables alone are enough.

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
PYTHONPATH=backend python -m organiser
```

That listens on `127.0.0.1:8000` and seeds the demo household when the task table is empty.

Terminal B:

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies the API, so leave `VITE_API_BASE_URL` empty.

For reload while editing the API:

```bash
PYTHONPATH=backend uvicorn organiser.main:app --reload --host 127.0.0.1 --port 8000
```

## One process, the shape of the house box

Build the UI, then let FastAPI serve `frontend/dist` and the API together.

```bash
cd frontend && npm ci && npm run build && cd ..
PYTHONPATH=backend python -m organiser
```

Open http://127.0.0.1:8000. `DEPLOY.md` is the later systemd note. This repo does not install it.

## Tests

Tests use PostgreSQL, never SQLite. They create `organiser_test` when the role is allowed to, and they do not read the demo database.

```bash
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
pytest
```

Start Compose Postgres first (`docker compose up db`) or point `TEST_DATABASE_URL` at another empty database:

```bash
TEST_DATABASE_URL=postgresql+psycopg://organiser:organiser@localhost:5432/organiser_test pytest
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
