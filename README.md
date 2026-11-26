# data/transfermarkt-recent

Temporary holding branch for recent Transfermarkt match data, scraped for **research use only**
(`research/tm_recent.py` and `docs/briefs/transfermarkt-recent-scrape.md` on the main development branch).
Not code. Like `data/api-football-raw`, to be moved to private storage and removed from history.

| File | Contents |
|---|---|
| `transfermarkt-recent/games.csv.gz` | finished matches 2026-07-07 to 2026-11-24 (1,296), shaped like the transfermarkt-datasets `games` table |
| `transfermarkt-recent/game_lineups.csv.gz` | line-ups for those matches |
| `transfermarkt-recent/appearances.csv.gz` | minutes, goals and cards per player per match (minutes derived from the match reports) |
| `transfermarkt-recent/game_events.csv.gz` | goals, substitutions and cards |
| `transfermarkt-recent/players.csv.gz` | players not in the third-party dataset (name, position, birth date, citizenship) |

The third-party dataset (transfermarkt-datasets, CC0) stops at 2026-07-06; these files continue it. They are scraped
from transfermarkt.com, not licensed. Spec §5 and ADR-0017 keep scraped data out of the production path, and the licence
question (ADR-0017, open point 1) is unsettled: do not build on this branch or treat it as published data. The cached raw
HTML pages are deliberately not included.
