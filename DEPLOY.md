# Later deploy note

This file is a sketch for a future change on the house Debian box. Nothing here is installed by this repo.

Discovery-system looks after that box. An agent working on this application must not add a systemd unit, a host user, firewall rules, packages on the box, or edits under `/etc`. Do not touch Cloudflare, tunnels, DNS, or `organiser.grok.me`.

## One machine

The house Debian box runs both parts:

- the FastAPI backend and the SQLite file
- the built Vite/React UI, served by that same FastAPI process

There is no separate frontend machine and no second hostname to fill in. Do not invent an IP or a host for the UI.

Local development can use two terminals (API and `npm run dev`) on one computer. The house install does not run the Vite dev server. It builds `frontend/dist` and serves it from FastAPI.

## Shape of a future install

A later change, owned by discovery-system, can:

1. Put the repo on the house Debian box, for example `/opt/daily-organiser`.
2. Create a virtualenv there and install `backend/requirements.txt`.
3. On that same box, build the UI (`npm ci && npm run build` in `frontend/`) with `VITE_API_BASE_URL` left empty, so the browser calls `/api` on the same origin.
4. Keep secrets in `/etc/daily-organiser.env` (mode `0600`), not in git. Start from `.env.example`. `HOST=127.0.0.1` if the tunnel is the only entry, or `HOST=0.0.0.0` for the home LAN as well.
5. Run one process as a dedicated user. The SQLite file stays on this machine (`DATABASE_PATH`).

Example unit discovery-system might install later (not part of this repo, not enabled here):

```ini
[Unit]
Description=Daily Organiser
After=network.target

[Service]
Type=simple
User=organiser
WorkingDirectory=/opt/daily-organiser/backend
EnvironmentFile=/etc/daily-organiser.env
ExecStart=/opt/daily-organiser/.venv/bin/python -m organiser
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

`python -m organiser` reads `HOST` and `PORT` from the environment file. FastAPI serves `/api` and the built files in `frontend/dist`.

## Cloudflare, later

`organiser.grok.me` is the public host. It uses the existing grok.me Cloudflare setup on this same house box. It is not configured in this repo.

When discovery-system adds it, a cloudflared ingress on that box can point the hostname at `http://127.0.0.1:8000` (the one process above). Leave `SESSION_HTTPS_ONLY=false` if the box is also opened over plain HTTP on the LAN. The browser session is a `SameSite=Lax` cookie on that origin.

## Data scope

Personal tasks and notes only. Do not point this service at work systems or at Hilton or guest data.
