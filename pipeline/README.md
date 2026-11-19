# pipeline

Quick Python path for match data, ahead of the Java ingestion-service (ADR-0017).
Every API response is fetched **once** and kept in Postgres. Everything downstream
(the rating job now, ingestion-service later) reads the database, never the API.

```
API-Football ──fetch.py──▶ raw_payloads ──normalize.py──▶ leagues, teams, fixtures,
   (once per request)        (as received)                  fixture_results, shootouts,
                                                             players, appearances
```

- `raw_payloads` is append-only: each response exactly as received, with its request.
- The other tables are derived. `normalize.py` truncates and rebuilds them from the
  latest stored response of each request, in one transaction, without API calls.

## Setup

```
pip install -r requirements.txt
createdb -h localhost -U market ingestion       # the Postgres of infra/compose.yml
export OPENELO_DB=postgresql://market:market@localhost:5432/ingestion   # the default
export APIFOOTBALL_KEY=...                       # your API-Football key
```

## Use

```
python fetch.py status                                  # quota; does not count
python fetch.py fixtures --league 39 --season 2024      # 1 request: all fixtures and scores
python fetch.py players  --league 39 --season 2024      # 1 request per finished match
python normalize.py
```

`fetch.py` skips any request already stored, so it can be re-run or resumed; it
waits 6.5 s between requests (the 10-a-minute limit) and stops two requests short of
the daily quota. `fixtures --refresh` stores a new version of a fixture list, for a
season still in progress. A response that reports an error is not stored.

League ids: Premier League 39, LaLiga 140, Serie A 135, Bundesliga 78, Ligue 1 61,
Champions League 2, Europa League 3, Conference League 848.

## Free plan

100 requests a day, 10 a minute, **seasons 2022 to 2024 only** (no current season),
no multi-match `ids` requests. A Premier League season is 1 fixtures request plus
380 player requests, about 4 days of quota.

## Data

The `appearances` table holds every matchday squad entry: starters, substitutes who
came on (their minutes) and unused substitutes (0 minutes), with the provider's
position (G, D, M, F), goals and assists. Results are goals after extra time; a
shoot-out is in `shootouts` and counts as a draw for the rating.

API data stays in the database; the repository is public, so none of it is committed.
