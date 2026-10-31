# Agent rules for daily-organiser

This is Nick's (Mykola's) personal organiser. The house Debian box, looked after by discovery-system, will run both the FastAPI backend and the React UI. It is not a work system. There is no separate frontend machine.

## Hard rules

1. Work on a feature branch and open a pull request to `main`. Branches and pull requests only.
2. Never push to `main`. Never merge to `main` from an agent. A person merges.
3. Do not change the host. No systemd units, users, firewall rules, packages on the Debian box, or edits under `/etc`.
4. Do not touch Cloudflare, tunnels, DNS, or `organiser.grok.me`. Discovery-system does that later, on the house box. See `DEPLOY.md`.
5. Home-only data. Tasks and notes are personal. Do not import, store, or connect Hilton, guest, hotel, or employer data. Do not put that data in fixtures, samples, or issues.
6. Never commit secrets, `.env`, or the SQLite database.
7. Do not add a second host for the UI, and do not invent hostnames or IP addresses.

## How to change the app

Keep it small: FastAPI, a SQLite file under `data/`, and the Vite + React app in `frontend/`. HTTP paths live in `frontend/src/api/`. Pages and components call those functions. Prefer straightforward code. Document new environment variables in `.env.example` or `frontend/.env.example`. Leave `VITE_API_BASE_URL` empty so the UI and API stay on one origin.
