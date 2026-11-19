# data/api-football-raw

Temporary holding branch for raw API-Football responses fetched by `pipeline/`
(see that folder on the main development branch). Not code; to be moved to private
storage and removed from history.

| File | Contents |
|---|---|
| `api-football/ingestion-2026-11-19.dump` | `pg_dump -Fc` of the `ingestion` database; `pg_restore -d ingestion <file>` |
| `api-football/raw_payloads-2026-11-19.jsonl.gz` | the same responses, one JSON object per line |

Contents as of 2026-11-19: Premier League 2024/25 fixture list (380 matches) and
squads for 3 matches.
