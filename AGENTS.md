# Agent rules for daily-organiser

Daily Organiser is a smart home organiser for Nick (Mykola). Tasks can be bot-reasoned and context-aware when that helps (a rota, or public transport, later). A plain task still works with zero extra fields: a title is enough, and `assist_mode` defaults to `when_useful` without asking.

Do not build live transport monitoring or curator routines unless a later PR says so. The hooks are `assist_mode` (`off` or `when_useful`), `context_hint`, and `source` (`manual` or `bot`) on tasks, plus `source` on notes. A bot may update status or add a note only after Nick says yes. This app does not ask that question yet, and it does not call a bot.

The house Debian box, looked after by discovery-system, will run both the FastAPI backend and the React UI. It is not a work system. There is no separate frontend machine.

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
