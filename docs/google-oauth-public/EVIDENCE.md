# Evidence for the public drafts

Reviewed again on 7 November 2026 after merging `origin/main` at `e5ce5d1` (PR 27, transcription model default). No Google, TfL, or Mistral call was made. The live refresh token, the live database, Cloudflare logs, and disk encryption were not inspected. Where the source is silent, the public pages say so.

PR 27 changes the default of `mistral_transcribe_model` from `voxtral-mini` to `voxtral-mini-transcribe-3`, and Compose sends that default when the variable is unset. A set value is still what is sent. Diary code, `morning_packet`, and the Mistral packet shape are not in that diff. The privacy page now names the new default. It does not change the calendar claims.

## What the calendar code does

| Behaviour | Where |
| --- | --- |
| Only these scopes are named: `calendar.events.readonly` and `calendar.calendarlist.readonly`. Comment: the refresh call does not send a scope, so this process cannot widen the grant. | `SCOPES` in `backend/organiser/services/diary.py` |
| Configured only when client id, client secret, and refresh token are all non-blank. | `Settings.diary_configured` in `backend/organiser/config.py` |
| Blank `GOOGLE_CALENDAR_IDS` means `primary`. Ids are a `SecretStr` and are not shown in the settings repr. | `calendar_id_list`, `Settings.calendar_ids` in `backend/organiser/config.py`; tests in `backend/tests/test_connections.py` |
| Refresh: `POST https://oauth2.googleapis.com/token` with `grant_type=refresh_token` and the three secrets. Access token cached in the module dict `_TOKEN` until near `expires_in` (default 3600). `clear_cache()` only clears that dict. | `_token`, `clear_cache` in `backend/organiser/services/diary.py` |
| Event read: `GET /calendar/v3/calendars/{id}/events` with `timeMin`, `timeMax`, `singleEvents=true`, `orderBy=startTime`, `maxResults=50`. No `fields` mask. | `_events` |
| Window is the local calendar day in `house_timezone` (default `Europe/London`). | `appointments_section` |
| Kept for the brief: stripped `summary` or `Busy`, local `HH:MM` or `All day`, and `sha256(event id)[:12]`. Cancelled events skipped. Duplicate ids skipped. | `appointments_section`, `_when` |
| Titles matching `outside_home` are dropped after the response is received. The same helper skips a calendar display name. | `outside_home` in `backend/organiser/agent/runner.py`; called from `appointments_section` and `add_calendar` |
| Block list is a fixed regular expression: Hilton, guest, colleague, employer, coworker, workplace, payroll, work email, work phone, at work. A personal hotel booking is not the same test. A title that misses the list is shown. | `_OUTSIDE_HOME_RE` in `backend/organiser/agent/runner.py` |
| Calendar list: `GET /calendar/v3/users/me/calendarList?maxResults=100`. No page token. Used when adding a calendar, not on every brief. | `_calendar_list`, `add_calendar` |
| Settings list stores `provider`, `calendar_id`, `display_name`. The API view returns the row id and the display name, not the Google id. | `CalendarSubscription` in `backend/organiser/models.py`; `calendar_view`; `POST/DELETE /system/calendars` via `add_calendar` / `remove_calendar` |
| Brief read does not insert a subscription row. The first add seeds the current configured calendars. | `add_calendar`, `_seed_current` |
| Diary outcome stored as `integration_status` name `diary`: `last_ok_at` or `last_error_class` `unconfigured` / `unavailable`. No body. | `_mark`; model `IntegrationStatus` |
| Failure log is the fixed info line `diary request failed` or `diary list failed`, not the exception. | `appointments_section`, `add_calendar` |
| HTTP helper comment: callers must not log the URL. | `backend/organiser/services/outbound.py` |
| Request log is method, path, status, duration. No body, query, or headers. httpx and httpcore log at warning. Tracebacks are stripped because they can carry a URL. Scrubber redacts secret assignments, UK postcodes, and coordinates. | `AccessLogMiddleware` in `backend/organiser/httpsec.py`; `configure_logging` and `scrub` in `backend/organiser/jsonlog.py` |
| Tests: read-only, dedupe, Hilton title absent from the brief and the log, tokens absent, no insert/patch/delete URL; scope strings present and write scopes absent; add and remove by name; primary default. | `backend/tests/test_sprint2.py`, `backend/tests/test_connections.py` |

There is no Google revoke route. Disconnect and revoke exist for X only (`disconnect` in `backend/organiser/x/oauth.py`, `POST /x/disconnect`). The Google token is not sealed with `X_TOKEN_KEY`.

## What reaches Mistral

| Behaviour | Where |
| --- | --- |
| Morning review builds the full brief, which reads the diary, then builds the packet. | `review` (`POST /agent/review`) in `backend/organiser/routes/agent.py` (`morning_brief` then `morning_packet`) |
| The packet copies only sections whose key is `tasks` or `commitments`. Appointments are skipped. | `morning_packet` in `backend/organiser/agent/runner.py` |
| Assistant tools `get_state`, `search_items`, and `get_item` read tasks, commitments, and counts. They do not read `CalendarSubscription` or call the diary. | `backend/organiser/agent/functions.py` |
| Context for Smart Add, catch-up, and follow-up is tasks, commitments, the log, and memory. The diary is not a context section. | `build_context` in `backend/organiser/agent/context.py` |
| Conversations are created with `store: true`. The runner deletes the conversation when the run ends and, on failure, logs the conversation id. | `MistralClient.start` in `backend/organiser/agent/mistral.py`; `iter_run` in `backend/organiser/agent/runner.py` |
| Voice, when `VOICE_INPUT_ENABLED` is on, can send one in-memory recording to Mistral. Words that look like an appointment are refused as a voice line. That refusal is not a calendar filter. | `backend/organiser/agent/voice.py` |

No test asserts that `morning_packet` omits appointments. The omission is the `if section["key"] not in ("tasks", "commitments")` branch. A later edit to that function would make the privacy page wrong.

Typed house-log text can still be sent to Mistral. The calendar code does not copy an event title into a task, a commitment, or a memory.

## What the pages refuse to promise

- That Google data is never received in a process that also calls Mistral. The morning review does both. The packet skips appointments.
- That Mistral, Google, Cloudflare, a journal, or a backup deletes anything on a schedule.
- That the refresh token or the database is encrypted at rest. Google’s OAuth policy asks for encrypted tokens and for revoke-then-delete. This code does not do that for Google.
- That the block list keeps work or guest events out of memory. It runs after the response, and only on the title or the calendar name.
- That the live token’s scopes match `SCOPES`. The token was not presented to Google.
- That nobody but the operator can open the brief. Access is outside this repo.
- That an in-app privacy notice already exists. The brief footnote is “Read only. This is not a calendar.”

## Unknown host behaviour

- Whether any `calendar_subscriptions` row exists in the house database.
- Which scopes the live refresh token actually has.
- Who is on the Cloudflare Access allow list.
- Cloudflare, tunnel, journal, crash-dump, and backup retention for the app host. The brief JSON crosses that host on its way to the browser.
- Whether the disk or the env file is encrypted.
- Whether `apidiscoverysolution.uk` is already verified in Search Console or listed as an authorized domain.
- The Cloud console’s sensitive-scope badge for these two scopes. Google’s sensitive-scope page uses reading Calendar events as an example. The fetched scope table does not print a badge.
- Whether Google will treat this External app as production or as personal use. The drafts do not rely on an exception.

## Official pages fetched for the requirements

- https://support.google.com/cloud/answer/15549049?hl=en
- https://developers.google.com/identity/protocols/oauth2/policies
- https://developers.google.com/identity/protocols/oauth2/scopes
- https://developers.google.com/workspace/calendar/api/auth
- https://developers.google.com/terms/api-services-user-data-policy
- https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification
- https://support.google.com/accounts/answer/13533235?hl=en

Acceptance is not guaranteed. See `HOSTING-PLAN.md` for the requirement table and the checks that still need a person.
