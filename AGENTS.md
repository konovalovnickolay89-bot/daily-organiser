# Agent rules for daily-organiser

Daily Organiser is Nick’s home operations log: events, tasks, commitments, and approvals. It is not a chat, and it is not the Bantō sidekick. Do not add a greeting, a wake word, or voice.

The arrival screen may say “Welcome home”. That line is a presence bar, not a conversation.

## Hard rules

1. Work on a feature branch and open a pull request to `main`. A person merges.
2. Never push to `main`. Never merge to `main` from an agent.
3. Do not change the host. No systemd install, no host user, no firewall, no packages on the Debian box, and no edits under `/etc`. `DEPLOY.md` is a note for later.
4. Do not touch Cloudflare, tunnels, DNS, or `organiser.grok.me`.
5. Home only. Tasks, commitments, events, and approvals are household life. Do not import, store, or connect Hilton, guest, hotel, or employer data. Do not put that data in fixtures or seed data.
6. Approvals stop at the log. Observe, advise, and prepare are stubs. Execute may be recorded and must not send, buy, book, or email. `effect_applied` stays false.
7. PostgreSQL is the database. Do not add SQLite. Compose must not publish `5432` or any other Postgres host port. Evolving Cook already owns `127.0.0.1:5432`. The only published port is the API on `127.0.0.1:8080`.
8. Never commit secrets or a `.env` file. The compose password is a local default only.
