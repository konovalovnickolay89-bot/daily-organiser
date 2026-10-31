# Daily Organiser

Personal tasks and notes for Nick (Mykola). Home data only: no work systems, and no Hilton or guest data.

The house Debian box (looked after by discovery-system) will run **both** this FastAPI backend and the Vite/React UI, on that one machine. There is no separate frontend host. The public name `organiser.grok.me` comes later, through the existing grok.me Cloudflare setup on that same box. This repo does not install a service, change the host, or configure Cloudflare. See `DEPLOY.md` and `AGENTS.md`.

## MVP

- **Tasks** have a title, due date, priority (`low` / `medium` / `high`), status (`todo` / `doing` / `done`, shown as To do / Doing / Done), and an optional recurring flag.
- **Notes** are quick text with tags, search, and an optional link to a task.
- **Today** lists tasks whose due date is the server's local date, plus recent notes.
- **Auth** is one shared password (`AUTH_SECRET`) and an `HttpOnly` session cookie.
- **Bind** address is `HOST` / `PORT`. `127.0.0.1` is this machine. `0.0.0.0` also opens the home LAN.

The recurring flag is stored and shown. It does not generate the next occurrence. Set the due date to the day you want the task to appear on Today.

Deleting a task keeps the note and clears the link.

## Project layout

```
backend/organiser/          FastAPI app (API, session, SQLite, built UI)
backend/tests/              API tests
frontend/src/api/           HTTP client. Pages call these functions, not raw URLs.
frontend/src/pages/         Today, Tasks, Notes, Login
frontend/src/components/    Presentational pieces for later screens
frontend/src/lib/           Labels, tag parsing, error text
frontend/.env.example       VITE_API_BASE_URL, left empty (same origin)
data/                       SQLite file at runtime (gitignored)
.env                        secrets, not committed
DEPLOY.md                   future single-box systemd + tunnel note
AGENTS.md                   branch, host, and data rules
```

The UI talks to the API through `frontend/src/api/`. Add new endpoints there when the app grows. Leave `VITE_API_BASE_URL` empty so the browser calls `/api` on the same origin as the page.

## Configure

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

Edit `.env` and set `AUTH_SECRET` to a long random string. The server refuses the placeholder.

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`SESSION_SECRET` is optional. If you leave it unset, the session cookie is signed with `AUTH_SECRET`. Set a different `SESSION_SECRET` when you want to change the password without invalidating existing sessions.

`DATABASE_PATH` defaults to `data/organiser.db`, relative to the repo root. Do not commit that file.

Leave `SESSION_HTTPS_ONLY=false` for plain HTTP on the LAN. The cookie is `SameSite=Lax` and lasts `SESSION_MAX_AGE` seconds (14 days by default).

## Run locally while developing

Two processes on the same computer. This is for editing. It is not a second server.

Terminal A, from the repo root:

```bash
source .venv/bin/activate
PYTHONPATH=backend python -m organiser
```

That reads `HOST` and `PORT` from `.env` (default `127.0.0.1:8000`). Equivalent if your shell is already in `backend/`:

```bash
python -m organiser
```

For reload while editing Python:

```bash
PYTHONPATH=backend uvicorn organiser.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Those `--host` and `--port` flags are the bind address for that command. The app still reads secrets and `DATABASE_PATH` from `.env`.

Terminal B:

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` to http://127.0.0.1:8000 so the session cookie stays on one origin. Do not open the built `index.html` as a file.

Interactive API docs: http://127.0.0.1:8000/docs

## Run as one process

This is the shape for the house box: one process serves the API and the built UI.

```bash
cd frontend
npm install
npm run build
cd ..
source .venv/bin/activate
PYTHONPATH=backend python -m organiser
```

Open http://127.0.0.1:8000. Build with `VITE_API_BASE_URL` unset (`frontend/.env.example`). Until `frontend/dist` exists, `/` is a 404 and the API still works.

## Use it

Log in with `AUTH_SECRET`.

| View | What it does |
| --- | --- |
| Today | Tasks due on the server's local date, and the latest notes. You can add either from this page. |
| Tasks | Create and filter tasks. Change status. Delete. |
| Notes | Capture a note, tag it, optionally link a task, and search. |

HTTP API (session required except health, login, and logout):

| Method | Path |
| --- | --- |
| GET | `/api/health` |
| POST | `/api/auth/login` `{ "password": "..." }` |
| POST | `/api/auth/logout` |
| GET | `/api/auth/me` |
| GET, POST | `/api/tasks` |
| GET, PATCH, DELETE | `/api/tasks/{id}` |
| GET, POST | `/api/notes` |
| GET, PATCH, DELETE | `/api/notes/{id}` |
| GET | `/api/today` |

Task list filters: `status`, `priority`, `due` (`YYYY-MM-DD`), `q`. Note list filters: `q`, `tag`, `task_id`. Today accepts `notes_limit` (default 20, max 100).

Status values are `todo`, `doing`, and `done`. Priority values are `low`, `medium`, and `high`.

## Tests

```bash
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
pytest
```

The tests use a temporary SQLite file and a fixed test secret. They do not read your real tasks.

## LAN, and what is not in this repo

Set `HOST=0.0.0.0` only on a trusted home network. This MVP has no second factor and no lockout, so use a long `AUTH_SECRET` and do not publish the port.

`organiser.grok.me`, systemd, and Cloudflare stay with discovery-system on the house box. `DEPLOY.md` is the sketch. Do not add them in an app change.

Python 3.12+ and Node 20+ (developed on Node 22). Frontend lockfile: `frontend/package-lock.json`.
