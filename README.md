# Daily Organiser

Home operations for Nick: a household log, a morning brief, and a quiet arrival screen. Tasks, commitments, and approvals carry an owner and a status. Events are the memory of what was recorded. The greeting can pause the house.

This is not a chat and not a sidekick. “Welcome home” is the arrival line, shown for one hour after the house records an arrival. At other times the greeting follows the clock in Europe/London. From 22:00 to 04:59 the headline is Good night; the date stays beside Home. Nothing here speaks, listens, or greets in a conversation. The morning brief stays the day’s tasks and commitments.

Approvals stop at the log. Observe, advise, and prepare update a status. Execute can be approved and still does nothing outside this database: no message, no purchase, no booking.

A Mistral assistant reads the log and proposes changes as cards. Apply makes exactly the change on the card to one task or commitment in this database; Not now dismisses it. Fixed rules decide when it speaks on its own. See [docs/mistral-agent.md](docs/mistral-agent.md).

Home only. No work systems, and no Hilton or guest data.

This is not a calendar. There is no month grid and no screen to create or edit a diary event. `/events` is the operational house log. A later brief may show today’s appointments as a read-only list. Applying a card does not write to a diary.

Apply is the only way a proposal changes the log. The allowlist is one task or one commitment: create it, edit it, or add a dated note. Approvals still only record a decision, and `effect_applied` stays false. Nothing is sent, bought, or booked.

A curator polls `GET /agent/activity` and may file one task card with `POST /agent/proposals`. That card waits for Apply. The request does not call Mistral.

Bantō is not connected. When a later sprint adds the commute push, the body is only `start`, `end`, and `location_label`. The label `Wembley` means Wembley Park. The origin is home. No names, no staff ids, and no guest or hotel text.

The live house is [https://organiser.apidiscoverysolution.uk](https://organiser.apidiscoverysolution.uk). Cloudflare Access is the only login. This app has no accounts. `organiser.grok.me` is not this service. See `DEPLOY.md` and [docs/SECURITY.md](docs/SECURITY.md).

Logs are JSON, one object a line. A request line is the method, the path, the status, and how long it took. It does not include the body, a postcode, a coordinate, or a secret.

## Layout

```
backend/organiser/        FastAPI service (Postgres, brief, approvals, pause)
backend/organiser/agent/  Mistral assistant: rules, functions, spec, client
backend/tests/            Schema and API tests
frontend/src/api/         The only place the UI calls the API
frontend/src/arrival/     Arrival shell, icon rail, and the module registry
frontend/src/modules/     Greeting, brief, approvals, proposed changes, today, quiet suggestion, catch-up
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

A later module is registered in `frontend/src/arrival/modules.js` and calls `frontend/src/api/`. Panels are `brief`, `approvals`, `today`, and `corner`. Any other panel is rendered under the cards.

## Run the whole stack

Docker Compose starts Postgres, the API, and the arrival screen. Postgres has no host port. It is reachable only as the hostname `db` on the compose network. Evolving Cook already listens on `127.0.0.1:5432` on the house box, so this file does not publish `5432` or any other Postgres port.

The only published port is the API on the host loopback. Inside the container the process listens on `0.0.0.0:8080` so Docker can forward that one address. It is not published on the LAN. The same process serves the built UI.

```bash
docker compose up --build
```

Open http://127.0.0.1:8080. `/docs` and `/openapi.json` stay off unless `ENABLE_DOCS=true` (local debug only).

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
| GET | `/health` | Process and database are up. The body includes `version` |
| GET, POST | `/tasks` | List and create. Filters: `status`, `priority`, `owner`, `due_on`, `scope=today` |
| GET, PATCH, DELETE | `/tasks/{id}` | One task |
| GET, POST | `/commitments` | List and create. Filter: `status`, `owner` |
| GET, PATCH, DELETE | `/commitments/{id}` | One commitment |
| GET, POST | `/events` | Operational log. Filter: `kind`, `owner` |
| GET, PATCH, DELETE | `/events/{id}` | One event |
| GET, POST | `/action-requests` | List and create. Filter: `status`, `mode`, `owner` |
| GET, PATCH, DELETE | `/action-requests/{id}` | One request. `effect_applied` cannot be set |
| GET | `/brief/morning` | Tasks due today or overdue, open commitments, read-only appointments, the shopping list, and weather |
| GET | `/approvals` | Pending requests. `status=all` lists every decision |
| POST | `/approvals/{id}/approve` | Status becomes approved. Nothing outside the log changes |
| POST | `/approvals/{id}/skip` | Status becomes skipped |
| GET | `/system` | Pause flag, activity, status line, and the presence-bar greeting |
| GET | `/system/facts` | Timezone, assistant on or off, the assistant switch, runs left today, and whether diary, weather location, TfL, and Bantō are configured. No secret, coordinate, postcode, or calendar id. Never calls Mistral |
| POST | `/system/assistant` | Persist the assistant switch. Body: `{"enabled": true}` or false. One activity line when it changes. Keys are not removed |
| GET, POST | `/shopping` | Shopping names. Create body is `{"name": "..."}` only. An extra field is rejected |
| POST | `/shopping/{id}/tick` and `/untick` | Mark a line got, or put it back. Nothing is ordered |
| GET, POST | `/system/calendars` | Diary names. Add body is `{"name": "..."}`. No provider id is returned |
| DELETE | `/system/calendars/{id}` | Remove one diary from the list |
| POST | `/system/pause` | Pause. Repeating it does not write a second log line |
| POST | `/system/unpause` | Resume |
| POST | `/system/arrive` | Record an arrival. “Welcome home” lasts one hour from the first signal. A repeat inside that hour does not extend it or write a second log line. Nothing is sent or booked |
| GET | `/agent` | Assistant state: on or off, paused, the review that is due, runs left today, last reply, waiting cards. Never calls Mistral |
| GET | `/agent/activity` | Recent house-log lines for a curator: `id`, `at` (Europe/London, ISO-8601), `text`, `type`. Query: `limit` (default 40, max 100), `since` (lines strictly after that time). Newest first. Never calls Mistral. Types include `add`, `apply`, `catchup`, `pause`, `resume`, `arrival`, `approval`, `proposal`, `note`, `assistant` |
| POST | `/agent/proposals` | One pending task card. Body: `title` (required), optional `due_on` (`YYYY-MM-DD`), `reason`, `source`. Does not create a task or call Mistral. 422 empty title, bad or past date, or anything outside the house. 409 paused, duplicate of an open task or commitment or a waiting card, or 10 cards already waiting. Apply and Not now are the routes below |
| POST | `/agent/feed` | One entry from the box. The assistant may propose up to 3 cards. 409 paused, 503 off, 429 runs used, 424 the assistant did not finish. `Accept: text/event-stream` sends the working steps, then the cards or one error. A failure is not a 502 |
| POST | `/agent/review` | Run the review `GET /agent` says is due. Each window runs once |
| POST | `/agent/proposals/{id}/apply` | Make exactly that change to one task, commitment, or shopping item, and log one line. 409 if paused, decided, or the item changed |
| POST | `/agent/proposals/{id}/dismiss` | Not now. A proactive item rests for 72 hours |
| GET | `/catch-up` | Pending catch-up cards, if any are showing. Does not record a look |
| POST | `/catch-up/look` | Record a look at the arrival screen. After a gap, prepare one catch-up |
| POST | `/catch-up/items/{id}/apply` | Add the note on that card to one task or commitment |
| POST | `/catch-up/items/{id}/dismiss` | Not now. That item rests for 72 hours |
| POST | `/commute/shift` | One shift: `start`, `end`, and `location_label` only. `Wembley` means Wembley Park. Origin is home. The same check the webhook uses. Nothing is booked |
| POST | `/hooks/{source}` | Signed inbound webhook. HMAC-SHA256 of `{timestamp}.{raw body}` with that source's secret, a timestamp header, and a five-minute window. A signature is accepted once in that window. Only `banto` / `commute` is registered. Unknown sources and events are refused and not stored |

Task status is `todo`, `doing`, or `done`. Priority is `low`, `medium`, or `high`. Commitment status is `open`, `kept`, or `dropped`. An action mode is `observe`, `advise`, `prepare`, or `execute`. An action status is `pending`, `approved`, or `skipped`. Owner defaults to `Nick`.

`scope=today` is the house date in `HOUSE_TIMEZONE` (default `Europe/London`): not done, due today or earlier. The morning brief also includes open tasks with no date. A task due later stays on the full list only.

Approve and skip return `effect.applied: false` and a short summary. The `action_requests.effect_applied` column is constrained to false.

## Arrival screen

One home screen. A thin icon rail on the left, a large greeting, then cream cards on a near-black canvas. Morning and evening use the same structure. Only the warm high-contrast colours shift. The greeting words still come from the house.

1. Rail: thin line icons for Home, Brief, tasks, approvals, Today, and Settings. No illustrations.
2. Greeting, large, at the top of the main area. The words come from `GET /system`: “Welcome home” for one hour after `POST /system/arrive`, otherwise Good morning (05:00–11:59), Good afternoon (12:00–16:59), or Good evening (17:00–21:59) in Europe/London. From 22:00–04:59 the headline is Good night, and the date stays beside Home. Status and Pause / Unpause sit with the greeting.
3. Cards: morning brief, Today, and the assistant column. Today includes the task list and the add line. The right-hand column is the working strip (Received, Reading the house log, Calling the assistant, Done or Failed) and then one Decisions list. Proposals and pending approvals share that list. Each card is Apply or Not now. Apply on a proposal makes the allowlisted change. Apply on an approval only records the decision. The next line replaces the strip. The strip shows “The assistant is off” until a key, an agent id, and the Settings switch are all on. The brief shows appointments (read only), shopping (names and ticks), and weather, or a short line when that section is not set.
4. Under the cards, only when `SHOW_PLAYLIST_STUB=true`: “A playlist is ready, when you want it.” The line is hidden by default. Text only. It does not play anything and it does not control the house.

Colour follows the house clock. Good morning and Good afternoon use the brighter morning theme. Good evening and Good night use the deeper evening theme. “Welcome home” follows the London hour. Settings can hold morning or evening in this browser. That only recolors the chrome.

After a gap, a quiet Catch up card sits under the greeting. It appears on the first look once the screen has been away for eight hours, or the last look was on an earlier London day. From 22:00 to 05:59 it stays hidden, and a look in those hours does not spend a gap that is already due. It stays hidden while the house is paused. At most four cards, one pass per gap: tasks that are overdue or due today, a task in progress with no update for three days, commitments due today or tomorrow, then anything else still unfinished on the brief. Apply adds one dated note to that task or commitment. Not now rests the item for 72 hours. Two screens share the one pass. Nothing is sent.

Pausing changes the greeting and writes one system event. It does not send or prepare anything. Approving while paused still only updates the log.

## Demo rows

When the task table is empty and `SEED_ON_START` is true, the API inserts a small household: bins, plants, a hallway bulb, a boiler reminder that is not booked, two open commitments, a kept one, and four pending decisions including an execute request that cannot send a message.

## Assistant

The assistant is off until `MISTRAL_API_KEY` and `MISTRAL_AGENT_ID` are set, and the Settings switch is on. The switch is stored on the house and writes one activity line. It does not delete the keys. `python -m organiser.agent sync` creates the agent in Mistral from `backend/organiser/agent/spec.py`; `show` prints the same values for Mistral's agent builder. [docs/mistral-agent.md](docs/mistral-agent.md) has the steps, the console values, and the rulebook.

It speaks when you write in the box, at a morning review (first look between 06:00 and 10:59), and about items that have gone quiet (in progress 3 days, 2 days overdue, a commitment due today or tomorrow). Smart Add and catch-up also build a typed context: the London time and theme, open tasks and commitments, the waiting list, a house-log window (3 days for Smart Add, 7 for catch-up), and an empty memory slot of 10. Anything outside the house is left out. Catch-up still chooses its cards in code. A commute also asks for a journey check; the journey source is not connected. Pause stops it. It raises at most 3 cards a day on its own, one at a time, and runs Mistral at most 12 times a day. A feed that does not finish returns 424 with a short line, and the screen keeps that line. Tests use a scripted fake and never reach Mistral.

## House file

discovery-system keeps secrets in the house environment file this app already uses. Do not add a second file. Older notes named `/etc/daily-organiser.env`; that is not a path this repo creates. `.env.example` lists the names with empty placeholders. Never commit a real key, postcode, or coordinate, and the API does not log them.

| Name | What a later sprint may use it for |
| --- | --- |
| `MISTRAL_API_KEY`, `MISTRAL_AGENT_ID` | Assistant. Empty keeps it off |
| `ENABLE_DOCS`, `DOCS_BEHIND_ACCESS` | Both false on the house. Docs are served only when both are true, and only behind Cloudflare Access |
| `HOUSE_LAT`, `HOUSE_LON` or `HOUSE_POSTCODE` | Weather location. Coordinates win when both are set; otherwise the postcode is resolved and not logged |
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REFRESH_TOKEN` | Read-only diary. Scopes are `calendar.events.readonly` and `calendar.calendarlist.readonly` |
| `GOOGLE_CALENDAR_IDS` | Which calendars to read until Settings stores a list. Blank means `primary` |
| `TFL_APP_KEY` | Journey check. Not connected yet |
| `BANTO_COMMUTE_TOKEN` | Shift push of start, end, and a location label. Not connected yet |
| `WEBHOOK_SECRET_BANTO` | HMAC secret for `POST /hooks/banto`. Empty keeps that door closed |
| `WEBHOOK_SECRET_BANTO_X` | Reserved for the X relay. Not a source yet. Leave empty |
| `SHOW_PLAYLIST_STUB` | `true` shows the quiet playlist line. Default is off. It still does not play |

The diary requests only `calendar.events.readonly` and `calendar.calendarlist.readonly`. It must not request a write scope. Settings shows calendar names, not ids. It never shows a token, a coordinate, or a postcode.

Weather comes from Open-Meteo. A postcode is turned into coordinates with postcodes.io and then forgotten. The brief credits Open-Meteo. If the location is missing, or either call fails, that section says so and the rest of the brief stays.

`/docs`, `/redoc`, and `/openapi.json` stay 404 unless `ENABLE_DOCS` and `DOCS_BEHIND_ACCESS` are both true. Leave both false on the house. Turning them on later is only for a host Cloudflare Access already covers.

Cloudflare Access has to cover the public hostname for both the arrival screen and the JSON routes, including `/agent` and `/system`. This repo does not change Cloudflare.

## What this does not do

No merge to `main`, no deploy, no Cloudflare change, no voice, no Bantō call, no playlist service, and no shopping that buys anything. The diary is a read-only list, not a calendar. The assistant proposes; it never sends, buys, books, or changes a row without Apply. Schema changes for a fresh database can use Alembic (`backend/alembic`, revision `0002_sprint2`). The running process still uses `create_all` plus a boot patch and does not replace a backup-and-upgrade on the live database.
