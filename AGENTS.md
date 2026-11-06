# Agent rules for daily-organiser

Daily Organiser is Nick’s home operations log: events, tasks, commitments, and approvals. It is not a chat, and it is not the Bantō sidekick. Do not add a greeting, a wake word, or voice.

The arrival screen may say “Welcome home”. That line is a presence bar, not a conversation.

The Mistral assistant is a box and a list of cards, not a conversation: one entry, one short reply in the voice of a log, and no thread. See `docs/mistral-agent.md`.

## Hard rules

1. Work on a feature branch and open a pull request to `main`. A person merges.
2. Never push to `main`. Never merge to `main` from an agent.
3. Do not change the host. No systemd install, no host user, no firewall, no packages on the Debian box, and no edits under `/etc`. `DEPLOY.md` is a note for later.
4. Do not touch Cloudflare, tunnels, DNS, or `organiser.grok.me`.
5. Home only. Tasks, commitments, events, and approvals are household life. Do not import, store, or connect Hilton, guest, hotel, or employer data. Do not put that data in fixtures or seed data.
6. Approvals stop at the log. Observe, advise, and prepare are stubs. Execute may be recorded and must not send, buy, book, or email. `effect_applied` stays false.
7. PostgreSQL is the database. Do not add SQLite. Compose must not publish `5432` or any other Postgres host port. Evolving Cook already owns `127.0.0.1:5432`. The only published port is the API on `127.0.0.1:8080`.
8. Never commit secrets or a `.env` file. The compose password is a local default only.
9. The Mistral assistant reads the log through `backend/organiser/agent/functions.py` and only proposes. It never writes a row itself. An explicit Apply tap may make one allowlisted change to one task, one commitment, or one shopping item (create it, edit it, or add a dated note; a shop item is a name only) in this database. Nothing leaves the house. Action requests and approvals still only record, and `effect_applied` stays false.
10. Rules in `backend/organiser/agent/rules.py` decide when the assistant runs. GET routes never call Mistral. Nothing runs or shows while the house is paused. `MISTRAL_API_KEY` lives only in the environment, never in git, fixtures, or logs. The agent's instructions and function schemas live in `backend/organiser/agent/spec.py`; change them there and sync, not by hand in Mistral's console.
