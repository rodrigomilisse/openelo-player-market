-- Staging schema for API-Football data (ADR-0017: raw payloads kept as received).
-- Applied by `migrate`; every statement is idempotent.

-- Every successful API response, append-only. This table is the ledger that stops
-- the loader asking twice: a request (endpoint + params) with a `final` row is never repeated.
CREATE TABLE IF NOT EXISTS raw_payload (
    id                 bigserial PRIMARY KEY,
    provider           text        NOT NULL DEFAULT 'API_FOOTBALL',
    endpoint           text        NOT NULL,
    params_key         text        NOT NULL,          -- canonical "a=1&b=2"
    params             jsonb       NOT NULL,
    body               jsonb       NOT NULL,
    results            integer     NOT NULL,
    final              boolean     NOT NULL,          -- complete: not fetched again unless --refetch
    received_at        timestamptz NOT NULL DEFAULT now(),
    requests_remaining integer
);
CREATE INDEX IF NOT EXISTS raw_payload_key ON raw_payload (provider, endpoint, params_key, final);

-- Requests the provider refuses for a lasting reason (plan does not cover a season).
-- Skipped on later runs so they cost nothing, until --retry-blocked.
CREATE TABLE IF NOT EXISTS fetch_block (
    endpoint   text NOT NULL,
    params_key text NOT NULL,
    reason     text NOT NULL,
    detail     text NOT NULL,
    blocked_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (endpoint, params_key)
);

CREATE TABLE IF NOT EXISTS league (
    league_id integer PRIMARY KEY, name text NOT NULL, country text
);
CREATE TABLE IF NOT EXISTS team (
    team_id integer PRIMARY KEY, name text NOT NULL
);
CREATE TABLE IF NOT EXISTS player (
    player_id integer PRIMARY KEY, name text NOT NULL
);
CREATE TABLE IF NOT EXISTS fixture (
    fixture_id   integer PRIMARY KEY,
    league_id    integer NOT NULL REFERENCES league,
    season       integer NOT NULL,
    round        text,
    kickoff      timestamptz NOT NULL,
    status       text NOT NULL,
    home_team_id integer NOT NULL REFERENCES team,
    away_team_id integer NOT NULL REFERENCES team,
    home_goals   integer,                -- after extra time, never shoot-out kicks
    away_goals   integer,
    extra_time   boolean NOT NULL,
    shootout     boolean NOT NULL,
    payload_id   bigint  NOT NULL REFERENCES raw_payload
);
CREATE INDEX IF NOT EXISTS fixture_league_season ON fixture (league_id, season);
CREATE INDEX IF NOT EXISTS fixture_kickoff ON fixture (kickoff);

-- One row per player listed in a match (starters and bench; minutes 0 when unused).
CREATE TABLE IF NOT EXISTS appearance (
    fixture_id integer NOT NULL REFERENCES fixture,
    player_id  integer NOT NULL REFERENCES player,
    team_id    integer NOT NULL REFERENCES team,
    started    boolean NOT NULL,
    minutes    integer NOT NULL,
    goals      integer NOT NULL,
    assists    integer NOT NULL,
    position   text,
    payload_id bigint  NOT NULL REFERENCES raw_payload,
    PRIMARY KEY (fixture_id, player_id)
);
CREATE INDEX IF NOT EXISTS appearance_player ON appearance (player_id);
