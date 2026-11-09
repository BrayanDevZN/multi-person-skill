# socialsim CLI reference

The `socialsim` CLI is the ONLY way to read or write the simulation database. Never open the SQLite file
directly and never write SQL for writes.

## Invocation

Run from the project root:

```
bin/socialsim <group> <command> [ID] [--json '<object>' | --file <path>] [flags]
```

- The first call bootstraps a virtualenv and installs dependencies (needs network once). Later calls are instant.
- The database is created automatically. `init` exists but you never have to call it.
- IDs are positive integers and are always positional (`persona get 5`).
- Payloads are JSON objects passed with `--json '...'` (wrap in SINGLE quotes) or `--file path.json`
  (`--file -` reads stdin). **Use `--file` whenever the payload contains an apostrophe or is long**
  (for example a `react_trace`). Write the file with the Write tool into the scratchpad directory.
- `--db <path>` (before the command) or the `SOCIALSIM_DB` env var selects another database file. Normally unused.

## Responses

Every call prints exactly one JSON line.

```
{"ok": true,  "data": ...}
{"ok": false, "error": "what went wrong", "hint": "how to fix it"}
```

- Exit code 0 = success, 1 = rejected input (read `error` and `hint`, fix, retry), 2 = usage error or unexpected failure.
- Validation is strict: unknown fields, wrong types and out-of-range values are rejected, never silently fixed.
- Batch writes (`persona create`, `reaction save`, `research add`) are all-or-nothing: if one item is invalid,
  nothing is saved. Fix the item and resend the whole batch.
- Deleting requires `--confirm`. Only delete when the user asked for it.

## Enumerations

| Field | Allowed values |
|---|---|
| `action` | `ignore`, `like`, `comment`, `share`, `click`, `convert`, `reject` |
| `sentiment` | `positive`, `neutral`, `negative` |
| reaction `status` (when saving) | `ok`, `failed` (`pending` is created by `run start`) |
| run `status` | `running`, `completed`, `partial` |
| `purchase_intent` | integer 0-10 |
| persona `age` | integer 13-100 |
| state `interest_level` | integer 0-10 |

Conversion rate in reports = share of OK reactions whose action is `convert`.
Engagement rate = share whose action is not `ignore`.

---

## Setup and inspection

### `init`
Create the database and tables. Idempotent. `bin/socialsim init`

### `schema`
Tables, columns and enum values. `bin/socialsim schema`

### `stats`
Row counts per table and runs by status. `bin/socialsim stats`

### `commands`
Machine-readable catalog of every command, its payload fields (type, required, range) and an example.
Run it whenever you are unsure about a field name. `bin/socialsim commands`

### `query`
Read-only ad-hoc SQL. Only a single `SELECT`/`WITH` is accepted; anything else is rejected.
Flags: `--sql "<statement>"` (required), `--limit N` (default 200).
Returns `{"rows": [...], "truncated": false}`.

```
bin/socialsim query --sql "SELECT segment, COUNT(*) AS n FROM personas GROUP BY segment"
```

### `export`
Dump a table. Flags: `--table` (`ideas|research|personas|persona_state|runs|reactions`),
`--format json|csv` (default json), `--out <file>` (otherwise the content is inside the JSON response).

```
bin/socialsim export --table reactions --format csv --out reactions.csv
```

---

## Ideas

An idea is the product or service being tested. Names are unique (case-insensitive).

### `idea create`
Fields: `name` (required), `description`, `ad_copy`. Returns the idea with its `id`.

```
bin/socialsim idea create --json '{"name": "Diet app", "description": "AI meal planner for busy people", "ad_copy": "Lose weight without counting calories. 7 days free."}'
```

If it fails with "already exists", reuse the existing idea: `idea list` with `q`.

### `idea get`
`bin/socialsim idea get 1` returns the idea plus its `research` entries and `runs`.

### `idea list`
Optional payload `{"q": "text"}` filters by name/description. Returns id, name, description, run and research counts.

```
bin/socialsim idea list --json '{"q": "diet"}'
```

### `idea update`
Partial update of `name`, `description`, `ad_copy`. `bin/socialsim idea update 1 --json '{"ad_copy": "New text"}'`

### `idea delete`
Deletes the idea AND its research, runs and reactions (personas are kept). `bin/socialsim idea delete 1 --confirm`

---

## Research

Findings from web research, linked to an idea, so the origin of every persona can be audited.

### `research add`
Fields: `idea_id`, `topic`, `finding` (all required), `source_url`. Accepts one object, a list, or `{"research": [...]}`.

```
bin/socialsim research add --json '{"research": [
  {"idea_id": 1, "topic": "competitors", "finding": "MyFitnessPal and Noom dominate; users complain about paywalls", "source_url": "https://example.com/a"},
  {"idea_id": 1, "topic": "audience", "finding": "Largest segment of new diet-app users is women 25-44, mostly on Instagram and TikTok"}
]}'
```

### `research list`
Optional `{"idea_id": 1}`. `bin/socialsim research list --json '{"idea_id": 1}'`

### `research delete`
`bin/socialsim research delete 3 --confirm`

---

## Personas

A persona is a reusable simulated social media user. Personas persist across runs and remember past exposures.

Fields (`name` and `age` required): `name`, `age`, `gender`, `occupation`, `income_level`, `location`, `segment`,
`bio`, `personality` (JSON object), `interests` (list of strings), `platforms` (list of strings),
`tags` (list of strings), `origin` (string such as `sim:diet-app` or `manual`).

### `persona create`
Accepts one object, a list, or `{"personas": [...]}`. All-or-nothing. Returns `{"created": [{"id", "name"}]}`.
Always run `persona search` first to avoid duplicates (see below).

```
bin/socialsim persona create --file personas.json
```

### `persona search`
Duplicate check. Compare a candidate profile with the existing personas. Fields (all optional but at least one
profile field is required): `age`, `gender`, `occupation`, `segment`, `location`, `interests`, `min_score` (default 3).

Returns `{"matches": [{"score", "likely_duplicate", "persona": {...}}], "duplicate_threshold": 7}`.
`likely_duplicate: true` (score >= 7) means "reuse that persona instead of creating a new one".

```
bin/socialsim persona search --json '{"age": 33, "gender": "female", "occupation": "designer", "segment": "busy professional"}'
```

### `persona list`
Filters (all optional): `min_age`, `max_age` (inclusive), `gender`, `segment`, `tag`, `origin`, `q` (free text over
name/occupation/bio/segment/location), `ids` (list), `reacted_idea_id` (only personas that already reacted to that idea),
`not_reacted_idea_id` (only personas that have NOT yet reacted to it). Flags: `--limit N`, `--full` (all fields).
Returns `{"total": N, "personas": [...]}`; compact rows by default.

```
bin/socialsim persona list --json '{"min_age": 30, "tag": "lote-1", "not_reacted_idea_id": 2}'
```

### `persona get`
`bin/socialsim persona get 5` returns every field, the persona's `state` (mood, interest_level, notes, `memory`
of past exposures) and its reaction `history` across all ideas.

### `persona update`
Partial update. `bin/socialsim persona update 5 --json '{"tags": ["lote-1", "fitness"]}'`

### `persona delete`
Also deletes the persona's state and reactions. `bin/socialsim persona delete 5 --confirm`

---

## Persona state

### `state get`
`bin/socialsim state get 5` returns `mood`, `interest_level`, `notes` and `memory`.
`memory` is a list of past exposures. It is appended automatically by `reaction save`; you rarely edit it.

### `state update`
Fields: `mood`, `interest_level` (0-10), `notes`, `memory_append` (one object appended to memory).

```
bin/socialsim state update 5 --json '{"mood": "stressed", "memory_append": {"note": "has been burned by subscription traps"}}'
```

---

## Runs

A run is one simulation round of one idea against a set of personas. Opening a run creates one `pending` reaction
per persona, which is what makes interrupted rounds resumable.

### `run start`
Fields: `idea_id`, `persona_ids` (non-empty list) both required, `notes`. Duplicate ids are collapsed.
Returns `{"run_id", "idea", "pending", "already_reacted_to_this_idea": [ids]}`.
Always call this BEFORE launching any persona agent.

```
bin/socialsim run start --json '{"idea_id": 1, "persona_ids": [1, 2, 3, 4], "notes": "autonomous pass"}'
```

### `run status`
`bin/socialsim run status 1` returns counts (`planned/ok/failed/pending`), `pending_persona_ids` and `failed` with errors.

### `run finish`
Closes the run: `completed` when every reaction is ok, otherwise `partial`. Optional `{"notes": "..."}`.
It does not change data, so it is safe to call again after more reactions are saved.

### `run resume`
Turns every `failed` reaction back into `pending`, sets the run to `running` and returns
`{"todo": [{"persona_id", "name"}]}`: the personas that still need simulating.

### `run list`
Optional `{"idea_id": 1, "status": "partial"}`. Flag `--limit N`.

### `run delete`
`bin/socialsim run delete 1 --confirm` (removes its reactions too).

---

## Reactions

One reaction per (run, persona). Saving the same pair again updates the row (idempotent).

### `reaction save`
Accepts one object, a list, or `{"reactions": [...]}`. All-or-nothing.

Fields: `run_id`, `persona_id` (required); `status` (`ok` default, or `failed`); `action`, `sentiment`,
`purchase_intent` (all three REQUIRED when status is `ok`); `comment`, `objections` (list of short strings),
`react_trace` (string); `error` (REQUIRED when status is `failed`).

Saving an `ok` reaction also appends the exposure to the persona's memory (replacing the entry of the same run).

```
bin/socialsim reaction save --file reactions.json
```

Failed simulation (bad output, timeout):

```
bin/socialsim reaction save --json '{"run_id": 1, "persona_id": 7, "status": "failed", "error": "agent returned invalid JSON twice"}'
```

### `reaction get`
`bin/socialsim reaction get 12` returns one reaction including its full `react_trace`.

### `reaction list`
Filters: `run_id`, `persona_id`, `idea_id`, `action`, `sentiment`, `status`, `min_intent`, `max_intent`.
Flags: `--limit N`, `--full` (include `react_trace`). Returns `{"total", "reactions": [...]}`.

```
bin/socialsim reaction list --json '{"run_id": 1, "sentiment": "negative"}'
```

### `reaction delete`
Removes one reaction by its reaction id (not the persona id). The persona's entry in `run` goes back to missing, so
prefer `reaction save` to overwrite a result. `bin/socialsim reaction delete 12 --confirm`

---

## Report

### `report run`
`bin/socialsim report run 1` returns the aggregated analysis of a run:
`counts`, `actions`, `sentiment`, `conversion_rate`, `engagement_rate`, `avg_purchase_intent`,
`top_objections` (normalised, with counts), `by_segment`, `by_age_group`,
`highlights.most_interested` / `least_interested` (with comments), `failed` and `pending_persona_ids`.
Rates are `null` when there are no OK reactions. Numbers in your final analysis must come from this report.
