# Mistral assistant

The assistant reads the house log and proposes changes. Each proposal is a card with **Apply** and **Not now**. Apply makes exactly the change on the card to one task or commitment in this database. Nothing is sent, bought, or booked, and nothing changes until you tap.

It speaks in two ways:

- **When you write in the box** on the arrival screen ("need filters for the boiler before Friday"). The right-hand column shows the working steps, then one or two lines and up to 3 cards. The next line replaces that strip. A commute or travel to work also asks for a card to check the journey. Nothing looks up live departures; the card says the journey source is not connected. If the run does not finish, the column says so and nothing is changed. That answer is HTTP 424, so the page stays in the app.
- **On its own, by fixed rules**: a morning review, and items that have gone quiet. The rules live in `backend/organiser/agent/rules.py`, not in the model.

## Set it up

The repo is the source of truth for the agent. One command creates the agent in Mistral, so the console and the code match.

1. In [Mistral's console](https://console.mistral.ai), open **API Keys** and create a key. This works from the phone.
2. On a laptop, put the key in `.env` at the repo root. Git ignores that file, and it keeps the key out of your shell history.

   ```bash
   MISTRAL_API_KEY=<your key>
   ```

3. From the repo root, create the agent. Either command works: Compose reads `.env` for the container, and the host command reads it directly.

   ```bash
   docker compose run --rm api python -m organiser.agent sync
   ```

   ```bash
   PYTHONPATH=backend python -m organiser.agent sync
   ```

   It prints a line like `MISTRAL_AGENT_ID=ag_…`. Add that line to `.env`. The agent now shows in the console's agent builder.
4. Start the app with `docker compose up --build` and write in the box.

Run `sync` again whenever `spec.py` changes. With `MISTRAL_AGENT_ID` set, it updates the same agent and Mistral keeps the earlier versions.

### Or fill in the console by hand

`python -m organiser.agent show` prints every value below, including the five function blocks for **Functions → Add**. No key is needed.

| Field in the agent builder | Value | Why |
| --- | --- | --- |
| Model | `mistral-medium-latest` | Good at calling functions, and it has the reasoning switch. `mistral-small-latest` costs less. |
| Built-in tools | **Search** on. Premium Search, Code and Image off. | Search covers web lookups (opening hours, prices, collection days). Nothing else is needed. |
| Reasoning effort | **High** | The judgement calls are the point: which date, duplicate or not, worth a card or not. Reviews run in the background, so the extra seconds cost nothing. |
| Functions | `get_state`, `search_items`, `get_item`, `propose_change`, `add_note` | Defined in `backend/organiser/agent/spec.py`. The app runs them. |
| Response format | Text | Proposals arrive as function calls, not as JSON. |
| Instructions | From `spec.py`, printed by `show` | The rulebook below, in the model's words. |

If replies to the box feel slow with High reasoning, set `MISTRAL_REASONING_EFFORT=` (empty) and sync again to leave it to the model's default.

## The rulebook

When the assistant may speak is decided in code. The model only words the run.

| Rule id | Fires when | Its job | At most |
| --- | --- | --- | --- |
| `feed` | You submit the box | Turn the text into tasks, commitments, dates or notes. Search first, so nothing is added twice. | 3 cards |
| `morning_review` | First screen read between 06:00 and 10:59 | Look over today's brief and propose next steps | Once a day, 2 cards |
| `doing_stalled` | A task in progress has had no update for 3 days | One fix: done, back to to-do, or a new date | 1 card |
| `overdue_lingering` | A task is 2 or more days overdue | One fix: done, a realistic date, or a first-step task | 1 card |
| `commitment_due_soon` | An open commitment is due today or tomorrow | One prep task, or kept | 1 card |

Always:

- **Pause is absolute.** While paused, nothing is sent to Mistral, no card is shown, and Apply waits.
- **Quiet hours.** No review runs between 22:00 and 05:59. The box works at any hour.
- **3 proactive cards a day.** What you write in the box does not count toward this.
- **12 Mistral runs a day** across everything, as a cost guard.
- **One proactive card at a time.**
- **Not now rests an item for 72 hours.** After a second look at the same item, it says nothing more until the item itself changes.
- **No screen, no review.** The display at home asks for a review when one is due. There is no scheduler and nothing is installed on the host.

### What Apply can change

| Card | Apply does |
| --- | --- |
| New task | Creates it: title, detail, due date, priority. Owner is Nick. |
| Task change | Sets any of title, detail, due date, priority, status |
| New commitment | Creates it, marked `source: assistant` |
| Commitment change | Sets any of title, detail, due date, status |
| Note | Adds one dated line to the item's detail |

Never: deleting, changing the owner, or anything outside this database. A date before today is refused. If the item changed after the card was made, Apply refuses and the card goes away. Each Apply writes one line to the house log.

## Settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `MISTRAL_API_KEY` | empty | With this empty, the assistant is off and nothing is sent |
| `MISTRAL_AGENT_ID` | empty | The `ag_…` id that `sync` printed |
| `MISTRAL_MODEL` | `mistral-medium-latest` | Used by `sync` |
| `MISTRAL_REASONING_EFFORT` | `high` | Used by `sync`. Empty leaves it to the model. |
| `AGENT_RUNS_PER_DAY` | `12` | Every Mistral run counts |
| `AGENT_PROACTIVE_PER_DAY` | `3` | Cards you did not ask for |

To turn it off, remove the key or the agent id and restart. The box then reads "The assistant is off."

## What leaves the house

- **Each run:** a short brief (the trigger, the house time, your text or the items to look at) and the results of the functions the model calls. Those results are household fields only: titles, details, dates and statuses.
- **Web search:** Mistral runs the query on its side. The instructions forbid names, addresses and other house details in a query.
- **Afterwards:** each conversation is deleted from Mistral when the run ends. The input and the reply stay at home in `agent_runs`.

## Going live on the house box

This is for discovery-system. The repo changes nothing on the host.

1. Cloudflare Access must guard the public hostname first. The app has no login. Without Access, anyone with the link could spend the key's credit and read the log through the assistant.
2. Add `MISTRAL_API_KEY` and `MISTRAL_AGENT_ID` to `/etc/daily-organiser.env` (mode `0600`).
3. The box needs outbound HTTPS to `api.mistral.ai`.
4. Reinstall `backend/requirements.txt` in the virtualenv: `httpx` is now a runtime dependency.

## Not yet

- **Memory (Graphiti).** It needs a graph database on the box, which is a host change for discovery-system.
- **Arrival and Sunday reviews.** These were not chosen.
