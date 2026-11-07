# Daily Organiser

Home operations for Nick: a household log, a morning brief, and a quiet arrival screen. Tasks, commitments, and approvals carry an owner and a status. Events are the memory of what was recorded. The greeting can pause the house.

This is not a chat and not a sidekick. “Welcome home” is the arrival line, shown for one hour after the house records an arrival. At other times the greeting follows the clock in Europe/London. From 22:00 to 04:59 the headline is Good night; the date stays beside Home. Nothing here speaks, listens, or greets in a conversation. The morning brief stays the day’s tasks and commitments.

Approvals stop at the log. Observe, advise, and prepare update a status. Execute can be approved and still does nothing outside this database: no message, no purchase, no booking.

A Mistral assistant reads the log and proposes changes as cards. Apply makes exactly the change on the card to one task or commitment in this database; Not now dismisses it. Fixed rules decide when it speaks on its own. See [docs/mistral-agent.md](docs/mistral-agent.md).

Home only. No work systems, and no Hilton, guest, colleague, or employer data. A personal hotel booking for the household can stay.

This is not a calendar. There is no month grid and no screen to create or edit a diary event. `/events` is the operational house log. A later brief may show today’s appointments as a read-only list. Applying a card does not write to a diary.

Apply is the only way a proposal changes the log. The allowlist is one task or one commitment: create it, edit it, or add a dated note. Approvals still only record a decision, and `effect_applied` stays false. Nothing is sent, bought, or booked.

A curator polls `GET /agent/activity` and may file one task card with `POST /agent/proposals`. That card waits for Apply. The request does not call Mistral. A date that has already passed stays on the card, with Apply, Not now, and the line “This date has passed.” It is not dismissed on its own.

The rota can push one commute with `POST /commute/shift`. The body is only `start`, `end`, and `location_label`, and the only label kept is `Wembley`, which means Wembley Park. The origin is home. No names, no staff ids, and no guest or hotel text are stored. The brief and `GET /commute/plan` then plan the journey out, arriving before the shift by `COMMUTE_ARRIVAL_BUFFER_MINUTES`, and the return, departing at or after the finish. The next shift in the coming 14 days is used, including one that runs overnight. A missing token or key leaves a short line and changes nothing else. Pre-departure disruption checks stay off until `COMMUTE_DISRUPTION_CHECKS` is set. See [docs/commute-plan.md](docs/commute-plan.md).

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
| GET | `/metrics` | Prometheus text: request counts and latency by route, Mistral calls, failures and latency, activity-poll age, and the pending-proposal count. No house text |
| GET | `/system/status` | Health, version, the last Mistral success, the last activity poll, and the database size in bytes. Never calls Mistral |
| GET | `/alerts` | In-app alert cards. One per kind. Nothing is sent |
| POST | `/alerts/{kind}/dismiss` | Hide the current incident of that kind. A later incident can show again |
| POST | `/voice/transcribe` | One recording, in memory, to text for the Smart Add box. 404 unless `VOICE_INPUT_ENABLED`. Nothing is saved until Add |
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
| GET | `/system/facts` | Timezone, assistant on or off, the assistant switch, runs left today, and whether diary, weather location, TfL, and Bantō are configured. `disruption_checks` is `not active` until `COMMUTE_DISRUPTION_CHECKS` is on. No secret, coordinate, postcode, or calendar id. Never calls Mistral |
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
| POST | `/agent/proposals` | One pending task card. Body: `title` (required), optional `due_on` (`YYYY-MM-DD`), `reason`, `source`. Does not create a task or call Mistral. 422 empty title, a bad date, or anything outside the house. A past date is kept, and the card says “This date has passed.” 409 paused, duplicate of an open task or commitment or a waiting card, or 10 cards already waiting. 429 when this process has taken 30 proposals in a minute. Apply and Not now are the routes below |
| POST | `/agent/feed` | One entry from the box. The assistant may propose up to 3 cards, including one shopping line (a name only; Apply adds it). 409 paused, 503 off, 429 runs used or more than 6 lines in a minute from this process, 424 the assistant did not finish. `Accept: text/event-stream` sends the working steps, then the cards or one error. A failure is not a 502. While Mistral is down the box is hidden |
| POST | `/agent/review` | Run the review `GET /agent` says is due. Each window runs once |
| POST | `/agent/proposals/{id}/apply` | Make exactly that change to one task, commitment, or shopping item, and log one line. 409 if paused, decided, or the item changed |
| POST | `/agent/proposals/{id}/dismiss` | Not now. A proactive item rests for 72 hours |
| GET | `/catch-up` | Pending catch-up cards, if any are showing. Does not record a look |
| POST | `/catch-up/look` | Record a look at the arrival screen. After a gap, prepare one catch-up. When the assistant is on, Mistral writes each note. If it is off or does not answer, the template is used and the card says “Fallback used” |
| POST | `/catch-up/items/{id}/apply` | Add the note on that card to one task or commitment |
| POST | `/catch-up/items/{id}/dismiss` | Not now. That item rests for 72 hours |
| POST | `/commute/shift` | One rota shift. Header `Authorization: Bearer <BANTO_COMMUTE_TOKEN>`. Body is only `start`, `end`, and `location_label`. The label must be `Wembley`. 503 when the token is unset, 401 when it does not match, 422 for any other field or label, 429 after 12 pushes in an hour from this process. Nothing but those three fields is stored. A repeat of the same three fields returns the same row |
| GET | `/commute/plan` | The next round trip in Europe/London: outward home to the destination arriving before the shift, return departing at or after the finish. No body. 200 with no shift as well. Does not store, send, or book, and does not call Mistral. Asks TfL only when `TFL_APP_KEY` is set and a shift needs a journey. Pre-departure checks run only when `COMMUTE_DISRUPTION_CHECKS` is on, only inside this read, and stay quiet from 22:00 to 05:59. There is no scheduler. Home and the destination are `configured` or `missing`, and `check` is `not_verified`. No coordinate, postcode, or stop id is returned |
| POST | `/hooks/{source}` | Signed inbound webhook. HMAC-SHA256 of `{timestamp}.{raw body}` with that source's secret, a timestamp header, and a five-minute window. A signature is accepted once in that window. `banto` / `commute` uses the shift check. `banto_x` accepts `x.bookmark`, `x.watch_match`, and `x.draft` when `X_ENABLED` is on. Unknown sources and events are refused and not stored |
| GET, POST | `/x/status`, `/x/connect`, `/x/callback`, `/x/disconnect` | X OAuth. Off unless `X_ENABLED`. Connect returns an authorize URL. The callback stores a sealed refresh token and redirects home. Disconnect revokes it |
| GET, POST | `/x/items`, `/x/poll`, `/x/items/{id}/apply`, `/x/items/{id}/dismiss`, `/x/items/{id}/post` | Bookmark and watch cards, and drafts. Poll respects the interval, `since_id`, and backoff. Apply keeps a line in the log. Post sends one draft only when `confirm` is true |
| GET | `/playlist` | Latest hearthis.at track when `PLAYLIST_SOURCE=hearthis`. Cached for an hour. No stream URL |

Task status is `todo`, `doing`, or `done`. Priority is `low`, `medium`, or `high`. Commitment status is `open`, `kept`, or `dropped`. An action mode is `observe`, `advise`, `prepare`, or `execute`. An action status is `pending`, `approved`, or `skipped`. Owner defaults to `Nick`.

`scope=today` is the house date in `HOUSE_TIMEZONE` (default `Europe/London`): not done, due today or earlier. The morning brief also includes open tasks with no date. A task due later stays on the full list only.

Approve and skip return `effect.applied: false` and a short summary. The `action_requests.effect_applied` column is constrained to false.

## Arrival screen

One home screen. A thin icon rail on the left, a large greeting, then cream cards on a near-black canvas. Morning and evening use the same structure. Only the warm high-contrast colours shift. The greeting words still come from the house.

1. Rail: thin line icons for Home, Brief, tasks, approvals, Today, and Settings. No illustrations.
2. Greeting, large, at the top of the main area. The words come from `GET /system`: “Welcome home” for one hour after `POST /system/arrive`, otherwise Good morning (05:00–11:59), Good afternoon (12:00–16:59), or Good evening (17:00–21:59) in Europe/London. From 22:00–04:59 the headline is Good night, and the date stays beside Home. Status and Pause / Unpause sit with the greeting.
3. Cards: morning brief, Today, and the assistant column. Today includes the task list and the add line. The right-hand column starts with the five newest lines from `GET /agent/activity?limit=5`, then the working strip (Received, Reading the house log, Calling the assistant, Done or Failed), then one Decisions list. That column is not a chat. Proposals and pending approvals share the list. Each card is Apply or Not now. A past due date adds “This date has passed.” and does not remove the card. Apply on a proposal makes the allowlisted change, including a shopping line. Apply on an approval only records the decision. The next line replaces the strip. The strip shows “The assistant is off” until a key, an agent id, and the Settings switch are all on, and “The assistant is down” when a call has just failed. The add line is hidden in both of those cases. The brief shows the commute, appointments (read only), shopping (names and ticks), and weather, or a short line when that section is not set.
4. Under the cards, when `PLAYLIST_SOURCE=hearthis`: the latest track from that hearthis.at profile (title, genre, artwork). A tap opens `permalink_url` in a new tab. Nothing is streamed. The line is on once a source is set, unless `SHOW_PLAYLIST=false`. If hearthis cannot be reached, the last cached track is kept, or the line says it is quiet.

Colour follows the house clock. Good morning and Good afternoon use the brighter morning theme. Good evening and Good night use the deeper evening theme. “Welcome home” follows the London hour. Settings can hold morning or evening in this browser. That only recolors the chrome.

After a gap, a quiet Catch up card sits under the greeting. It appears on the first look once the screen has been away for eight hours, or the last look was on an earlier London day. From 22:00 to 05:59 it stays hidden, and a look in those hours does not spend a gap that is already due. It stays hidden while the house is paused. At most four cards, one pass per gap: tasks that are overdue or due today, a task in progress with no update for three days, commitments due today or tomorrow, then anything else still unfinished on the brief. When the assistant is on, one Mistral completion writes the notes. If it is off, down, or the reply cannot be used, the template note is kept and the card shows “Fallback used”. Apply adds that one dated note to that task or commitment. Not now rests the item for 72 hours. Two screens share the one pass. Nothing is sent. The wording call is not an agent run and does not spend the daily cap.

Pausing changes the greeting and writes one system event. It does not send or prepare anything. Approving while paused still only updates the log.

## Demo rows

When the task table is empty and `SEED_ON_START` is true, the API inserts a small household: bins, plants, a hallway bulb, a boiler reminder that is not booked, two open commitments, a kept one, and four pending decisions including an execute request that cannot send a message.

## Assistant

The assistant is off until `MISTRAL_API_KEY` and `MISTRAL_AGENT_ID` are set, and the Settings switch is on. The switch is stored on the house and writes one activity line. It does not delete the keys. `python -m organiser.agent sync` creates the agent in Mistral from `backend/organiser/agent/spec.py`; `show` prints the same values for Mistral's agent builder. [docs/mistral-agent.md](docs/mistral-agent.md) has the steps, the console values, and the rulebook.

It speaks when you write in the box, at a morning review (first look between 06:00 and 10:59), and about items that have gone quiet (in progress 3 days, 2 days overdue, a commitment due today or tomorrow). Smart Add, catch-up, and those follow-ups build a typed context, schema version 1: the London time and theme, open tasks and commitments, the waiting list, a house-log window (3 days for Smart Add, 7 for catch-up and follow-ups), a follow-up's focus line, and up to 10 memories chosen by similarity and recency. The home-scope filter runs once at build time. A token budget then drops the log, waiting cards, commitments, tasks, and memories, in that order. The log line is the counts. A postcode or a coordinate is never included. “Remember …” and “forget …” in the box wait for Apply. Settings lists, searches, pins, forgets, and exports that memory. Anything outside the house is left out. Catch-up still chooses its cards in code; when the note cannot be written by the assistant the card says “Fallback used”. A commute in the box can still propose a trip. The live journey is the brief, from the rota push, not a guess on the card. Pause stops it. It raises at most 3 cards a day on its own, one at a time, and runs Mistral at most 12 times a day. This process also refuses more than 6 box lines in a minute. A feed that does not finish returns 424 with a short line, and the screen keeps that line. If Mistral cannot be reached, the add line hides for about a minute and a half. Tests use a scripted fake and never reach Mistral.

## House file

discovery-system keeps secrets in the house environment file this app already uses. Do not add a second file. Older notes named `/etc/daily-organiser.env`; that is not a path this repo creates. `.env.example` lists the names with empty placeholders. Never commit a real key, postcode, or coordinate, and the API does not log them.

| Name | What it is for |
| --- | --- |
| `MISTRAL_API_KEY`, `MISTRAL_AGENT_ID` | Assistant. Empty keeps it off |
| `VOICE_INPUT_ENABLED` | Mic on Smart Add. Default off. Start recording, then Stop and transcribe (sends that clip to Mistral) or Cancel recording (does not upload). Audio is not stored. Text waits in the box until Add |
| `MISTRAL_TRANSCRIBE_MODEL` | Optional. Default `voxtral-mini-transcribe-3`. Used only when voice is on. A set value replaces the default |
| `ENABLE_DOCS`, `DOCS_BEHIND_ACCESS` | Both false on the house. Docs are served only when both are true, and only behind Cloudflare Access |
| `HOUSE_LAT`, `HOUSE_LON` or `HOUSE_POSTCODE` | Weather and the commute origin. Coordinates win when both are set; otherwise the postcode is resolved and not logged or stored |
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REFRESH_TOKEN` | Read-only diary. Scopes are `calendar.events.readonly` and `calendar.calendarlist.readonly` |
| `GOOGLE_CALENDAR_IDS` | Which calendars to read until Settings stores a list. Blank means `primary` |
| `TFL_APP_KEY` | Journey check for a Wembley commute, outward and return. Empty leaves “Journey check is not connected.” Register a free Unified API key and put it only in the house file |
| `BANTO_COMMUTE_TOKEN` | Bearer for `POST /commute/shift`. Empty leaves the push unwired and the brief says the commute is not connected |
| `COMMUTE_ARRIVAL_BUFFER_MINUTES` | Minutes before the shift to arrive. Default 10. Clamped to 0–180 |
| `COMMUTE_RETURN_BUFFER_MINUTES` | Minutes after the finish before the return departs. Default 0, which is at the finish. Clamped to 0–180 |
| `COMMUTE_PREDEPARTURE_MINUTES` | Window before the outward leave. Default 90. Clamped to 15–240. Used only when disruption checks are on |
| `COMMUTE_DISRUPTION_CHECKS` | Default false. The admin gate for the in-app pre-departure check. Off means no check and the screen says it is not active. On does not add a scheduler, a send, or a booking |
| `COMMUTE_DESTINATION_LABEL`, `COMMUTE_DESTINATION_STOP` | Optional pair. Both empty keeps Wembley Park (`940GZZLUWYP`). A partial pair is ignored. Do not put a postcode or a workplace name here |
| `RATE_COMMUTE_DISRUPTION_PER_HOUR` | Optional. Default 6. Cap for the pre-departure check in this process. The journey read is separate |
| `WEBHOOK_SECRET_BANTO` | HMAC secret for `POST /hooks/banto`. Empty keeps that door closed |
| `WEBHOOK_SECRET_BANTO_X` | HMAC secret for `POST /hooks/banto_x`. Empty keeps that door closed. Events are `x.bookmark`, `x.watch_match`, and `x.draft`, and only while `X_ENABLED` is on |
| `X_ENABLED` | X off unless `true`. Bookmarks, the watch list, and confirmed posts |
| `X_CLIENT_ID`, `X_CLIENT_SECRET` | Nick's X app. OAuth 2.0 with PKCE. Scopes: `tweet.read`, `users.read`, `bookmark.read`, `tweet.write`, `offline.access` |
| `X_REDIRECT_URI` | Must match the app. `https://organiser.apidiscoverysolution.uk/x/callback` |
| `X_TOKEN_KEY` | Fernet key. Refresh tokens are sealed with it. Never logged |
| `X_POLL_MINUTES` | Bookmark and watch poll. Default 30 |
| `PLAYLIST_SOURCE` | `hearthis` shows the playlist line. Empty hides it |
| `HEARTHIS_PROFILE` | hearthis.at profile. Default `chlorophil` |
| `SHOW_PLAYLIST` | Empty means on once a source is set. `false` hides the line. It still does not play |
| `RATE_FEED_PER_MINUTE` | Optional. Default 6. Burst limit for the box, in this process |
| `RATE_INGEST_PER_MINUTE` | Optional. Default 30. Burst limit for `POST /agent/proposals` |
| `RATE_COMMUTE_PER_HOUR` | Optional. Default 12. Burst limit for the shift push |

The diary requests only `calendar.events.readonly` and `calendar.calendarlist.readonly`. It must not request a write scope. Settings shows calendar names, not ids. It never shows a token, a coordinate, or a postcode.

Weather comes from Open-Meteo. A postcode is turned into coordinates with postcodes.io and then forgotten. A full postcode is tried first. A 404 tries the outcode, so a district code still resolves, and that miss is logged at warning without the value. The brief credits Open-Meteo. If the location is missing, or either call fails, that section says so and the rest of the brief stays.

The commute uses the same house point. TfL’s journey planner is asked for an arrival at Wembley Park station (`940GZZLUWYP`) before the shift start, by `COMMUTE_ARRIVAL_BUFFER_MINUTES` (default 10), in the London wall clock, and for a departure back home at the finish plus `COMMUTE_RETURN_BUFFER_MINUTES` (default 0). Line status for that journey is read with it. A shift that ends the next morning keeps the return on that finish. The next shift that has not ended, within 14 days, is the one shown, so a later day is not dropped just because today is empty. `2026-03-29` and `2026-10-25` follow Europe/London: a naive time that does not exist, or that happens twice, is refused until the push sends an offset. The two 01:30s on the autumn change are different instants and both may be stored. Buffer arithmetic is done in UTC so those gaps are not invented. The key, the coordinates, and the postcode are not logged and not written on the shift. Home and the destination are reported as configured when the values are nonempty, and as not verified: this app does not ask a provider to confirm them. Outbound HTTPS, when the key is set: `api.tfl.gov.uk`. A postcode also uses `api.postcodes.io`, as weather does.

Pre-departure disruption checks are a separate in-app note. They stay off until `COMMUTE_DISRUPTION_CHECKS` is set in the house file. There is no new process and no timer. A read during quiet hours (22:00–05:59 London) or while the house is paused does not call TfL for that note. A fresh note is kept for two minutes, a failed newer read can show the last note for 30 minutes and says so, and this process allows `RATE_COMMUTE_DISRUPTION_PER_HOUR` (default 6) of those calls. Nothing is sent or booked. [docs/commute-plan.md](docs/commute-plan.md) has the admin gate and the seams with the open line-status and settings pull requests.

`/docs`, `/redoc`, and `/openapi.json` stay 404 unless `ENABLE_DOCS` and `DOCS_BEHIND_ACCESS` are both true. Leave both false on the house. Turning them on later is only for a host Cloudflare Access already covers.

Cloudflare Access has to cover the public hostname for both the arrival screen and the JSON routes, including `/agent` and `/system`. This repo does not change Cloudflare.

## What this does not do

No merge to `main`, no deploy, no Cloudflare change, no wake word, no spoken reply, no playlist service, and no shopping that buys anything. The mic on Smart Add stays off unless `VOICE_INPUT_ENABLED`, and it only fills the box. The diary is a read-only list, not a calendar. The assistant proposes; it never sends, buys, books, or changes a row without Apply. The commute push does not book a train. Alert cards stay in the app. Schema changes for a fresh database can use Alembic (`backend/alembic`, revision `0005_sprint6`). The running process still uses `create_all` plus a boot patch and does not replace a backup-and-upgrade on the live database.
