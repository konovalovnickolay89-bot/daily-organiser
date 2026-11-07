# Commute plan

Round trip for the next household shift. This is a reading. It does not store a journey, send a message, book a seat, or call Mistral.

## What it shows

`GET /commute/plan` and the commute section of the morning brief share one plan.

- Outward: home to the destination, arriving `COMMUTE_ARRIVAL_BUFFER_MINUTES` before the shift starts. Default 10. `0` arrives at the start.
- Return: destination to home, departing `COMMUTE_RETURN_BUFFER_MINUTES` after the finish. Default `0`, which is at the finish, so the return is not planned before the shift ends.
- Clocks are Europe/London. The minutes are added in UTC, then shown in London, so the 29 March 2026 gap and the repeated hour on 25 October 2026 are not invented.
- A shift that starts one evening and ends the next morning keeps the return on the finish instant.
- The shift used is the earliest one that has not finished and that starts within 14 days. Today being empty does not hide tomorrow. A finished shift does not block a later one.
- The stored push is unchanged: `POST /commute/shift` still accepts only `start`, `end`, and `location_label`, keeps only `Wembley`, and returns the same row when those three match.

Home is the existing `HOUSE_LAT` and `HOUSE_LON`, or else `HOUSE_POSTCODE`. The destination defaults to Wembley Park. Set both `COMMUTE_DESTINATION_LABEL` and `COMMUTE_DESTINATION_STOP` to use another station. A label without a stop id, or a stop id without a label, is ignored and is not echoed. Do not put a home address, a postcode, or a workplace name in those two settings.

## Configured is not verified

| Place | `state` | `check` |
| --- | --- | --- |
| Nothing set for home | `missing` | `not_verified` |
| Coordinates or a postcode present | `configured` | `not_verified` |
| Coordinates present but not usable as numbers | `unusable` | `not_verified` |
| Destination, including the Wembley Park default | `configured` | `not_verified` |

`not_verified` means this app did not ask TfL or a geocoder to confirm the place. A nonempty value is not a verification. The plan never returns `verified`. It also does not return a coordinate, a postcode, or a stop id.

## Pre-departure checks

The admin gate is one environment value, off by default:

```
COMMUTE_DISRUPTION_CHECKS=false
```

Leave it false. The screen then says “Pre-departure disruption checks are not active.” Settings shows “Not active”. No extra TfL call is made for that note.

To turn the note on, a person sets `COMMUTE_DISRUPTION_CHECKS=true` in the house file and restarts the process. That is the whole gate. This repository does not set it, and this change does not deploy.

While the flag is on:

- The check runs only inside `GET /commute/plan` or the morning brief. There is no new process, timer, or scheduler.
- It runs only in the window of `COMMUTE_PREDEPARTURE_MINUTES` (default 90) before the outward leave.
- From 22:00 to 05:59 London it does not call TfL. The note says it is held for quiet hours and that nothing was sent.
- A paused house does not call TfL for the note.
- A fresh note is reused for 2 minutes. A failed newer read can keep the last note for 30 minutes and says the newer read failed. It is not described as live.
- This process allows `RATE_COMMUTE_DISRUPTION_PER_HOUR` calls (default 6). The cache holds at most four notes and does not hold the key.
- The note stays in the app. Nothing is sent, booked, or handed to the assistant as a new run.

The journey read that already fills the brief, when `TFL_APP_KEY` is set, is unchanged in kind: it still asks for the trip. That is separate from the gated pre-departure note.

## What this does not do

- No database migration. `commute_shifts` stays `id`, `start_at`, `end_at`, `location_label`.
- No live TfL, Mistral, Google, or postcodes call from the tests. Production calls TfL only when the key is set and a read needs a journey, and calls the disruption URL for the new note only when the flag is on.
- No change to proactive runs or memory.
- No host, Cloudflare, or secret change.

## Alembic

PR 21 adds `backend/alembic/versions/0007_settings_search.py`. PR 23 adds `backend/alembic/versions/0007_x_poll_pause.py`. Those two revisions share the number `0007`. This branch adds no revision and does not run Alembic. A later schema change has to pick a free revision after those two are reconciled, and only after a backup of the live database. That gate is not this pull request.

## Seams with open pull requests

This branch is taken from `main` at `e5ce5d1823e7a6c5d9ee37ca02e55cfd993ea358` (PR 27). It does not contain PR 28, PR 21, or PR 23.

**PR 28** (TfL line status on Home) is independent. It adds a Lines row and `GET /tfl/status`. This branch adds a Commute row and `GET /commute/plan`. They read different routes. When both are merged, the Home order should be Brief, Commute, Lines, Today, Proposed changes, Decisions. PR 28 also edits the same sentence in `AGENTS.md` rule 10 (to mention `GET /tfl/status`) and removes the Settings line “The journey source is not connected.” This branch replaces that line with the disruption-check sentence and adds the commute sentence to rule 10. Keep both sentences. Do not drop the Lines row or the Commute row.

**PR 21** adds `tfl_outcome()` in `backend/organiser/services/commute.py`, wrapping the old `_fetch` success path and the old `commute_section` failure path. This branch replaced that one-way fetch with `fetch_leg` and builds the brief from `commute_plan.section_for_brief`. On a merge, call the outcome note after a successful `fetch_leg`, and the attention note when the outward leg fails. PR 21 also inserts `FeatureSettings` in `ThemeCard` after the diary paragraph. Keep that insert and this branch’s diary sentence.

**PR 23** is the X card and `0007_x_poll_pause`. It does not share the commute route. The revision number is the collision above. Do not rename or absorb that file here.

No force-push and no rebase of history that has already been pushed.
