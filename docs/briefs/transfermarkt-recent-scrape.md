# Brief: bring the research data from 6 July 2026 to today by scraping Transfermarkt

Written 2026-11-25 for a session running on the owner's own machine (the cloud session's network
policy blocks transfermarkt.com). Read this whole file first; it is meant to be self-contained.

## Goal

The OpenElo research data (matches, line-ups, minutes) stops at **2026-07-06**. The owner needs it up to
today to judge the player ratings against their own current knowledge of who is playing well. Build a
scraper for Transfermarkt match data from 2026-07-07 onward and put the result into the same tables
the model already reads, then into Postgres schema `research`.

## Decision already made by the owner (do not re-ask)

- Spec §5 and ADR-0017 say live data must come from licensed APIs and scraped data stays out of the
  production path. The owner **explicitly overrides this for research use only**: the data is for
  validating the formula by hand, it goes in Postgres schema `research`, and it is never part of the
  production data path. Keep it that way: nothing here may be imported by a service.
- Be a polite client: one request at a time, at least 3 s between requests, back off on 429/5xx, stop
  on repeated blocks. Never hammer the site.

## Why this has to be built (what exists and what does not)

- `research/ingest.py` does **not** scrape. It downloads finished CSVs published by a third party
  (github.com/dcaribou/transfermarkt-datasets, CC0) from
  `https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/{table}.csv.gz`. Those files were last rebuilt
  2026-09-05 and contain nothing after 2026-07-06. The other source (Club-Football-Match-Data mirror) has team
  results only (to 2026-09-03), no players. No free source has recent line-ups or minutes.
- The only Transfermarkt code in the repo is `research/tm_client.py` (player search and market-value
  history). It has nothing for matches. Reuse its patterns (headers, retry, lxml XPath) but not its scope.
- The upstream project used a separate scraper (dcaribou/transfermarkt-scraper) that is **not** in this repo.
  Its per-match minutes come from per-player performance pages, which is too many requests. Derive minutes
  from the match report instead (below).

## What the model needs per match

Match ids are Transfermarkt's own: `game.game_id` is the number in
`https://www.transfermarkt.com/spielbericht/index/spielbericht/{game_id}`. Player and club ids are
Transfermarkt's too (`/spieler/{id}`, `/verein/{id}`), the same ids as the existing tables, so new rows join
to old ones with no mapping.

Read `research/ingest.py` (`load_games`, `load_appearances`, `load_lineups`, `load_players`, `SCHEMA`) before
writing anything: they define the exact columns, the derived fields (stage, leg, neutral, shootout, goal
difference, `data_issue`) and the competition list. Read `research/FINDINGS.md` §3 for the data rules
(shoot-out kicks are not part of the score; extra time counts; a team cannot play twice in a day).

Needed for every new match in a competition that is in the store's `competition` table
(65 competitions; the ten top leagues in `candidate.TOP_LEAGUES` matter most: GB1 ES1 IT1 L1 FR1 PO1 NL1 BE1 TR1 SC1,
plus UEFA competitions CL, EL, UCOL and domestic cups present in the table):

| Table | Source on Transfermarkt |
|---|---|
| `game` | competition schedule page `/{slug}/gesamtspielplan/wettbewerb/{COMP_ID}/saison_id/{YEAR}` gives game ids, dates, teams, scores; the match report gives the rest (extra time, penalties, round) |
| `lineup` | match report: starting eleven and bench, per team, with position |
| `appearance` | derived from the match report: starters play 90 (120 with extra time) unless substituted off or sent off; substitutes play from their entry minute to the end or their own exit/red card; unused bench = 0. Also goals, assists, yellow, red per player from the events |
| `player` | any player id not already in the store: `/spieler/{id}` for name, position, date of birth, citizenship |

Optional, lower priority (not needed for ratings, useful for the owner's comparison): current market values
(`ceapi/marketValueDevelopment/graph/{id}`, already handled in `tm_client.py`) and 2026 summer transfers.

Season id: Transfermarkt's `saison_id` is the year the season starts (2025 = 2025/26, 2026 = 2026/27).
Fetch 2025 only for matches after 2026-07-06 (late finals, play-offs) and 2026 in full.

## Design

1. `research/tm_recent.py`, a command with `--since 2026-07-07` (default: the day after the newest club match
   in the store) and `--competitions` to limit scope. Standard-library plus `requests` and `lxml` (already in
   `requirements.txt`); no new dependencies.
2. Cache every fetched page under `research/data/raw/downloads/transfermarkt-recent/pages/` (gitignored with the
   rest of `data/raw/`). A page already on disk is never fetched again; `--refetch` is explicit. Matches in the
   future or not finished are not fetched. A finished match is final.
3. Resumable: kill it at any time and the next run continues. Print progress and a one-line summary.
4. Output: write **tables shaped like the third-party CSVs** (`games`, `game_lineups`, `appearances`, `players`)
   to `research/data/raw/downloads/transfermarkt-recent/*.csv.gz`, then change `ingest.py` to load them after
   the main dataset with the same `load_*` functions. Where both have a game id, the main dataset wins (it will
   include the match once upstream catches up). This means `make update` (which rebuilds the store from
   downloads) keeps the scraped rows instead of wiping them.
5. Then `make store` and `make publish` in `research/` rebuild the store and ratings, and
   `python -m apisports_loader import-research` (in `services/ingestion-service/loader/`) copies the new rows
   into Postgres `research` (idempotent; only new rows are added).

## Verification (required before calling it done)

- **Minutes derivation check:** pick 30+ matches from the last weeks of the existing dataset (2026-06 / 2026-05),
  scrape them with the new code and compare per player: minutes, started, goals, assists, cards. Report the
  agreement. Differences above a few minutes per player need explaining (stoppage time handling) or a fix.
- Row sanity on the new data, using the rules already in `FINDINGS.md` §3 and the validation list in ADR-0017
  decision 8 (eleven starters per side, minutes 0 to 150, no player listed twice, substitutions that add up).
  Matches failing a rule are listed in `data_issue`, not silently dropped or fixed.
- Coverage: matches per competition per week against the schedule pages; list gaps.
- After the rebuild: `make status` shows the new newest match date; `research/data/raw/published/latest.csv`
  has ratings as of the new date; spot-check a few current stars (the owner knows these well) and report
  anything surprising.
- Tests for the parsers on saved HTML fixtures (save a few real pages as fixtures; no network in tests).

## Constraints and traps

- `ingest.py` runs in isolated mode (`python -I`) and imports nothing from the research directory. Keep it that
  way; put shared logic in the CSV format, not in imports.
- `ingest.build()` unlinks and recreates the store, so scraped data must live in `downloads/`, never only in
  the sqlite file.
- Do not commit anything under `data/raw/` (public repository, scraped data).
- Transfermarkt markup changes; keep all selectors in one place at the top of `tm_recent.py`, like
  `tm_client.py` does, and fail loudly (not with empty rows) when a page does not parse.
- Respect robots and rate limits; if the site starts blocking, stop and tell the owner instead of rotating
  IPs or disguising the client.
- The model's identity rule: a player's rating depends on minutes shares, so wrong minutes silently skew
  ratings. When unsure about a match's minutes, mark it with `data_issue` rather than guess.

## Current repo state (for orientation)

- Branch `claude/epic-johnson-vedn9p`. `research/Makefile`: `make warmup | update | publish | history | status`.
  `research/publish.py` rates all active players with the current candidate (settings at its top).
- Store: `research/data/raw/openelo_research.sqlite3` (built by `ingest.py` then `national.py`), newest club
  match 2026-07-06, 88,769 games, 1.89 M appearances, 3.18 M line-up rows.
- Postgres loader: `services/ingestion-service/loader/` (`import-research` copies the store into schema
  `research`; `history` and `recent` fill schema `public` from API-Football, currently blocked by an
  account suspension that is unrelated to this task).
- Data on a fresh machine: `cd research && make warmup` (downloads about 300 MB, ~15 min) recreates the store.
