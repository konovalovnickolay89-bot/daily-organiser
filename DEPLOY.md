# Later deploy note

This is a sketch for the house Debian box. Nothing in this file is installed by the repo. An agent must not add a unit under `/etc`, create a host user, or change firewall, packages, Cloudflare, or DNS.

Discovery-system looks after that box. The public name `organiser.grok.me` comes later, on that box, through the existing grok.me Cloudflare setup. It is not configured here.

## One machine

The house box runs:

- PostgreSQL on the same machine
- one FastAPI process, which also serves the built arrival screen from `frontend/dist`

There is no second hostname for the UI. Do not invent an IP. Local development may use Docker Compose or two processes. The house install does not need the Vite dev server, and it does not need the compose UI container.

## Shape of a future install

A later change, owned by discovery-system, can:

1. Put the repo on the box, for example `/opt/daily-organiser`.
2. Install PostgreSQL and create a database and user. Keep the password out of git.
3. Create a virtualenv and install `backend/requirements.txt`.
4. On that same box, build the UI (`npm ci && npm run build` in `frontend/`) with `VITE_API_BASE_URL` left empty, so the browser calls the API on the same origin.
5. Keep secrets in `/etc/daily-organiser.env` (mode `0600`). Start from `.env.example`. Set `DATABASE_URL`, `SEED_ON_START=false` once real household rows exist, and `HOST=127.0.0.1` if a tunnel will be the only entry.
6. Run one process as a dedicated user, after PostgreSQL is up.

Example unit discovery-system might install later. It is not part of this repo and it is not enabled here:

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
EnvironmentFile=/etc/daily-organiser.env
ExecStart=/opt/daily-organiser/.venv/bin/python -m organiser
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

`python -m organiser` reads `HOST` and `PORT` from the environment (default `127.0.0.1:8000`). The static files are found from the package path (`frontend/dist` next to `backend/`), not from the working directory. Build them before starting the unit. Until `frontend/dist/index.html` exists, `/` is a short JSON pointer and `/health` still works.

`SEED_ON_START=true` fills an empty task list with household demo rows. Turn it off after real tasks exist, or the next empty database will be filled again.

## Cloudflare, later

When discovery-system adds it, a cloudflared ingress on that box can point `organiser.grok.me` at `http://127.0.0.1:8000`. Do not add that ingress in an application change.

## Data scope

Personal household records only. Do not point this service at work systems or at Hilton or guest data. Approvals record a decision. They do not send, buy, or book.
