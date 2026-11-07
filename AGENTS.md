# Agent rules for daily-organiser

Daily Organiser is Nick’s home operations log: events, tasks, commitments, and approvals. It is not a chat, and it is not the Bantō sidekick. Do not add a greeting, a wake word, or a spoken reply. A microphone on Smart Add stays off unless `VOICE_INPUT_ENABLED`, and it only fills the box.

The arrival screen may say “Welcome home”. That line is a presence bar, not a conversation.

The Mistral assistant is a box and a list of cards, not a conversation: one entry, one short reply in the voice of a log, and no thread. See `docs/mistral-agent.md`.

## Hard rules

1. Work on a feature branch and open a pull request to `main`. A person merges.
2. Never push to `main`. Never merge to `main` from an agent.
3. Do not change the host. No systemd install, no host user, no firewall, no packages on the Debian box, and no edits under `/etc`. `DEPLOY.md` is a note for later.
4. Do not touch Cloudflare, tunnels, DNS, or `organiser.grok.me`.
5. Home only. Tasks, commitments, events, and approvals are household life. Do not import, store, or connect Hilton, guest, colleague, employer, or work-system data. A personal hotel booking for the household may be stored. Do not put Hilton, guest, colleague, employer, or work-system data in fixtures or seed data.
6. Approvals stop at the log. Observe, advise, and prepare are stubs. Execute may be recorded and must not send, buy, book, or email. `effect_applied` stays false. The one send is a confirmed Post on an `x.draft` card, and only when `X_ENABLED` is on.
7. PostgreSQL is the database. Do not add SQLite. Compose must not publish `5432` or any other Postgres host port. Evolving Cook already owns `127.0.0.1:5432`. The only published port is the API on `127.0.0.1:8080`.
8. Never commit secrets or a `.env` file. The compose password is a local default only.
9. The Mistral assistant reads the log through `backend/organiser/agent/functions.py` and only proposes. It never writes a row itself. An explicit Apply tap may make one allowlisted change to one task, one commitment, or one shopping item (create it, edit it, or add a dated note; a shop item is a name only), or one memory (save a remembered line, or delete only the memories confirmed on a forget card) in this database. Apply on an X bookmark or a watch match only keeps that line in this log. An explicit Post on one `x.draft`, after confirm, may send that one post when `X_ENABLED` is on. Refresh tokens stay encrypted with `X_TOKEN_KEY` and are revoked on disconnect. Nothing else leaves the house. Action requests and approvals still only record, and `effect_applied` stays false.
10. Rules in `backend/organiser/agent/rules.py` decide when the assistant runs. GET routes never call Mistral. `POST /catch-up/look` may ask Mistral for the note wording and falls back to the template when it cannot. Smart Add and that catch-up may ask Mistral for embeddings when filling the memory slot; if that call cannot be made, retrieval uses words. `POST /voice/transcribe` may send one in-memory recording to Voxtral when `VOICE_INPUT_ENABLED` is on, and it returns text only. Audio is not written, stored, or logged. A postcode or a coordinate is never sent. Nothing runs or shows while the house is paused. `GET /playlist` may read hearthis.at and caches that for an hour. `GET /commute/plan` and the morning brief may read TfL for the outward and return journey when `TFL_APP_KEY` is set. They do not call Mistral. Pre-departure disruption checks stay off unless `COMMUTE_DISRUPTION_CHECKS` is on, run only inside that read, and do not send or book. There is no scheduler for them. `POST /x/poll` may read X when `X_ENABLED` is on. `MISTRAL_API_KEY` lives only in the environment, never in git, fixtures, or logs. The agent's instructions and function schemas live in `backend/organiser/agent/spec.py`; change them there and sync, not by hand in Mistral's console.
