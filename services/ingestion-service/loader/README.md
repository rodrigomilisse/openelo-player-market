# apisports_loader

Fills a Postgres database with API-Football match data, slowly, and **never fetches the same
thing twice**. Every response is stored in Postgres first (`raw_payload`, append-only); before any
request the loader looks there, and only asks the API when Postgres has no complete answer.

```
cd services/ingestion-service/loader
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export DATABASE_URL='postgresql://USER:PASS@your-rds-host:5432/openelo?sslmode=require'
export APISPORTS_KEY='...'                 # not needed where a proxy injects it
.venv/bin/python -m apisports_loader migrate    # creates the tables (safe to repeat)
```

## Commands

| Command | What it does |
|---|---|
| `history` | Adds completed seasons, newest first, one league-season at a time: its fixture list (1 request), then each played match's players and minutes (1 request each). Stops when the budget or the day's quota runs out. Run it again tomorrow and it carries on where it stopped. |
| `recent` | Adds the latest matches: one request per day for the fixtures of every competition, then the players of each played match in the tracked leagues. A day is final once all its matches are over; an open day is asked again next time, a finished one never. |
| `status` | Per league and season: played matches, matches with players stored, matches still missing; the day's API quota. |
| `import-research` | Copies the research store (the Transfermarkt data the Elo model was built on: matches, line-ups, minutes, valuations, transfers, national teams, ~6 million rows) into Postgres schema `research`, with the model's own ids. Safe to repeat: rows already there are skipped, so after `make update` in `research/` it adds only what is new. `--replace transfer` reloads a table that has no primary key. |
| `rebuild` | Re-derives the tables from the stored responses. No API requests. |
| `migrate` | Creates or updates the tables. |

```
history --max-requests 90          # use at most 90 requests this run
history --max-matches 40           # stop after the players of 40 matches
history --league 39 --season 2022  # only one league and season
history --from-season 2020         # how far back to go (default 2018)
recent --days 7                    # default; or --since 2026-11-01
--reserve 3                        # always leave this many of the day's requests unused (default 3)
```

The quota is read at the start from the API's free `/status` call and from the headers of every
response. The per-minute limit is respected by waiting.

## What "never twice" means

- A complete response in `raw_payload` is never requested again. `history` also skips matches whose players are stored.
- A request the plan refuses (a season the plan does not cover) is remembered in `fetch_block` and costs nothing next time. `--retry-blocked` asks again.
- Only `--refetch` repeats anything, and `history --refetch` refuses to run without `--league` and `--season`. It adds a new row; the old payload stays.
- Not complete, so asked again: a day's fixtures while a match that day is not over, and for `recent` an empty players answer until the match is 72 hours old (line-ups can arrive late).

## Data

Two sources, two schemas, because their ids differ. Schema `research` is the scraped Transfermarkt data the
model uses today, up to the newest club match in the research store (2026-07-06 at the time of writing).
Schema `public` is API-Football (licensed), filled by `history` and `recent`. ADR-0017 keeps scraped data out of
the production path, so treat `research` as the model's training and validation set until the licence question is settled.

Tables: `league`, `team`, `player`, `fixture` (score after extra time, never shoot-out kicks; `extra_time`, `shootout`),
`appearance` (one row per player listed in a match: `started`, `minutes`, `goals`, `assists`, `position`; unused substitutes have 0 minutes).
Ids are API-Football's. They are **not** the Transfermarkt ids the research model uses (`research/`); mapping them is
the open identity question in ADR-0017.

## On AWS

Point `DATABASE_URL` at the RDS instance (`sslmode=require`; allow the loader's IP in the security group; keep the password in Secrets Manager or the scheduler's secret store, not in the repo). Nothing here creates the AWS resources. To run on a schedule, run `recent` daily and `history` daily until it reports everything is stored (for example from a scheduled container task or any cron host).

## Suspended account

API-Sports suspends accounts whose requests arrive from a shared IP (serverless and cloud platforms). If any command stops with
"account is suspended", the loader cannot fix it: reinstate the account on the API-Sports dashboard and send requests
from a dedicated static IP, for example through the Cloud Run proxy in their guide
("Avoid rate-limit and suspension issues with shared IPs"). Then set:

```
export APISPORTS_BASE='https://YOUR_PROXY_URL'      # replaces https://v3.football.api-sports.io
export APISPORTS_PROXY_TOKEN='...'                  # sent as Authorization: Bearer
```

## Tests

```
TEST_DATABASE_URL='postgresql://...' .venv/bin/python -m pytest tests   # needs a throwaway Postgres; it drops the public schema
```
