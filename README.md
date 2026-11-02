# Daily Organiser

Home operations for Nick: a household log, a morning brief, and a quiet arrival screen. Tasks, commitments, and approvals carry an owner and a status. Events are the memory of what was recorded. The presence bar can pause the house.

This is not a chat and not a sidekick. “Welcome home” is the arrival line, shown for one hour after the house records an arrival. At other times the presence bar follows the clock in Europe/London. From 22:00 to 04:59 the headline is Good night; the date is already on the bar. Nothing here speaks, listens, or greets in a conversation. The morning brief stays the day’s tasks and commitments.

Approvals stop at the log. Observe, advise, and prepare update a status. Execute can be approved and still does nothing outside this database: no message, no purchase, no booking.

A Mistral assistant reads the log and proposes changes as cards. Apply makes exactly the change on the card to one task or commitment in this database; Not now dismisses it. Fixed rules decide when it speaks on its own. See [docs/mistral-agent.md](docs/mistral-agent.md).

Home only. No work systems, and no Hilton or guest data.

The house Debian box will run this later as PostgreSQL plus one process. `organiser.grok.me` is not set up here. See `DEPLOY.md`.

## Layout

```
backend/organiser/        FastAPI service (Postgres, brief, approvals, pause)
backend/organiser/agent/  Mistral assistant: rules, functions, spec, client
backend/tests/            Schema and API tests
frontend/src/api/         The only place the UI calls the API
frontend/src/arrival/     Arrival shell and the module registry
frontend/src/modules/     Presence bar, brief, approvals, proposed changes, today, quiet suggestion, catch-up
docker-compose.yml        Internal Postgres; API and UI on 127.0.0.1:8080 only
docs/mistral-agent.md     Assistant setup, console values, and the rulebook
DEPLOY.md                 systemd sketch for later; nothing is installed
```

```
browser  →  arrival UI
               │  REST, same origin
               ▼
            FastAPI  →  PostgreSQL
               │        tasks, commitments, events, action_requests, system_state,
               │        agent_runs, agent_proposals
               ▼  HTTPS, only from POST /agent/feed and POST /agent/review
            Mistral (agent and web search)
```

A later module is registered in `frontend/src/arrival/modules.js` and calls `frontend/src/api/`. The shell (`ArrivalShell.jsx`) already has slots: `primary` (left), `secondary` (right), and `corner`.

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
| GET | `/system` | Pause flag, activity, status line, and the presence-bar greeting |
| POST | `/system/pause` | Pause. Repeating it does not write a second log line |
| POST | `/system/unpause` | Resume |
| POST | `/system/arrive` | Record an arrival. “Welcome home” lasts one hour from the first signal. A repeat inside that hour does not extend it or write a second log line. Nothing is sent or booked |
| GET | `/agent` | Assistant state: on or off, paused, the review that is due, runs left today, last reply, waiting cards. Never calls Mistral |
| POST | `/agent/feed` | One entry from the box. The assistant may propose up to 3 cards. 409 paused, 503 off, 429 runs used, 502 Mistral failed |
| POST | `/agent/review` | Run the review `GET /agent` says is due. Each window runs once |
| POST | `/agent/proposals/{id}/apply` | Make exactly that change to one task or commitment, and log one line. 409 if paused, decided, or the item changed |
| POST | `/agent/proposals/{id}/dismiss` | Not now. A proactive item rests for 72 hours |
| GET | `/catch-up` | Pending catch-up cards, if any are showing. Does not record a look |
| POST | `/catch-up/look` | Record a look at the arrival screen. After a gap, prepare one catch-up |
| POST | `/catch-up/items/{id}/apply` | Add the note on that card to one task or commitment |
| POST | `/catch-up/items/{id}/dismiss` | Not now. That item rests for 72 hours |

Task status is `todo`, `doing`, or `done`. Priority is `low`, `medium`, or `high`. Commitment status is `open`, `kept`, or `dropped`. An action mode is `observe`, `advise`, `prepare`, or `execute`. An action status is `pending`, `approved`, or `skipped`. Owner defaults to `Nick`.

`scope=today` is the house date in `HOUSE_TIMEZONE` (default `Europe/London`): not done, due today or earlier. The morning brief also includes open tasks with no date. A task due later stays on the full list only.

Approve and skip return `effect.applied: false` and a short summary. The `action_requests.effect_applied` column is constrained to false.

## Arrival screen

One home screen, in a dark charcoal palette: a thin centred presence bar, then two quiet panes.

1. Presence bar across the top, centred. The headline comes from `GET /system`: “Welcome home” for one hour after `POST /system/arrive`, otherwise Good morning (05:00–11:59), Good afternoon (12:00–16:59), or Good evening (17:00–21:59) in Europe/London. From 22:00–04:59 the headline is Good night, and the date stays beside Home. The status and Pause / Unpause stay on the bar.
2. Left: morning brief. Tasks and open commitments come from the API. Appointments, shopping, and weather are labelled as not connected.
3. Right: pending approvals, proposed changes, then a short Today list. Proposed changes has one input line for the assistant and its cards, each with Apply and Not now. It shows “The assistant is off” until a key and an agent id are set.
4. Corner: “A playlist is ready, when you want it.” It is text only. It does not play anything and it does not control the house.

After a gap, a quiet Catch up strip sits under the presence bar. It appears on the first look once the screen has been away for eight hours, or the last look was on an earlier London day. From 22:00 to 05:59 it stays hidden, and a look in those hours does not spend a gap that is already due. It stays hidden while the house is paused. At most four cards, one pass per gap: tasks that are overdue or due today, a task in progress with no update for three days, commitments due today or tomorrow, then anything else still unfinished on the brief. Apply adds one dated note to that task or commitment. Not now rests the item for 72 hours. Two screens share the one pass. Nothing is sent.

Pausing changes the presence bar and writes one system event. It does not send or prepare anything. Approving while paused still only updates the log.

## Demo rows

When the task table is empty and `SEED_ON_START` is true, the API inserts a small household: bins, plants, a hallway bulb, a boiler reminder that is not booked, two open commitments, a kept one, and four pending decisions including an execute request that cannot send a message.

## Assistant

The assistant is off until `MISTRAL_API_KEY` and `MISTRAL_AGENT_ID` are set. `python -m organiser.agent sync` creates the agent in Mistral from `backend/organiser/agent/spec.py`; `show` prints the same values for Mistral's agent builder. [docs/mistral-agent.md](docs/mistral-agent.md) has the steps, the console values, and the rulebook.

It speaks when you write in the box, at a morning review (first look between 06:00 and 10:59), and about items that have gone quiet (in progress 3 days, 2 days overdue, a commitment due today or tomorrow). Pause stops it. It raises at most 3 cards a day on its own, one at a time, and runs Mistral at most 12 times a day. Tests use a scripted fake and never reach Mistral.

## What this does not do

No merge to `main`, no deploy, no Cloudflare, no voice, no Bantō call, no live weather, no playlist service, and no shopping that buys anything. The assistant proposes; it never sends, buys, books, or changes a row without Apply.
