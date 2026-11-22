# ingestion-service

Anti-corruption layer for external football data: it fetches matches from a
provider, validates and translates them, and produces the `match.completed` v1
event (ADR-0017). This first cut maps live data from the free
[football-data.org](https://www.football-data.org) API and serves it over HTTP,
so a frontend can be tested against real matches. No database, outbox or Kafka
yet — those wait for ADR-0017's delivery work.

The `MatchSource` port is provider-neutral; football-data.org is one adapter
behind it. Swapping in a licensed provider later is a new adapter, not a change
to the domain.

## Running

Get a free API token (emailed in a minute) from
<https://www.football-data.org/client/register>, then:

```
FOOTBALL_DATA_TOKEN=your-token ./mvnw spring-boot:run
```

The token is read from the environment and never committed. The service listens
on `http://localhost:8081`.

## Endpoints

```
GET /matches?competition=PL&from=2026-03-01&to=2026-03-14   # finished matches, as match.completed
GET /matches/{sourceMatchId}                                # one match, as match.completed
GET /ping
```

`competition` is a football-data.org code (`PL`, `CL`, `PD`, `SA`, `BL1`, `FL1`,
…). `from`/`to` are `yyyy-MM-dd`; the free tier allows a window up to 10 days.

## Free-tier limits

- **No line-ups**, so `players` and `corners` come out empty. The rating formula
  falls back to the result alone, as research does for matches without that
  data. Per-player minutes need a paid tier or a provider that includes
  line-ups.
- 10 calls/minute. A 403 means the token is missing or invalid; a 429 means the
  rate limit was hit. Both surface as a 502 with the upstream status in the body.
- `stage` mapping from football-data.org's names onto the formula's stages is a
  placeholder (ADR-0017 open point 6); `venue` defaults to `HOME`.
