# ingestion-service

Adapters to external football data APIs (mocked for now). Acts as an anti-corruption layer: validates untrusted external data, then publishes `match.completed`.

The API-Football loader (history and recent commands, Postgres) is in [loader/](loader/README.md).
