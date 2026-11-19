-- Ingestion database: raw API responses, stored once, and the tables rebuilt from them.
-- Raw payloads are append-only facts (ADR-0017 decision 6). Everything below them is
-- derived and rebuilt by normalize.py, so it can be dropped and recomputed at any time
-- without calling the API again.

CREATE TABLE IF NOT EXISTS raw_payloads (
    id          bigserial   PRIMARY KEY,
    provider    text        NOT NULL,            -- 'api-football'
    endpoint    text        NOT NULL,            -- '/fixtures', '/fixtures/players'
    params      jsonb       NOT NULL,            -- the query, e.g. {"league": 39, "season": 2024}
    body        jsonb       NOT NULL,            -- the response exactly as received
    received_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS raw_payloads_request ON raw_payloads (provider, endpoint, params);

-- Derived tables (normalize.py truncates and rebuilds them in one transaction).

CREATE TABLE IF NOT EXISTS leagues (
    league_id   integer PRIMARY KEY,
    name        text    NOT NULL,
    country     text    NOT NULL
);

CREATE TABLE IF NOT EXISTS teams (
    team_id     integer PRIMARY KEY,
    name        text    NOT NULL
);

CREATE TABLE IF NOT EXISTS fixtures (
    fixture_id   integer     PRIMARY KEY,
    league_id    integer     NOT NULL REFERENCES leagues,
    season       integer     NOT NULL,           -- the year the season starts (2024 = 2024/25)
    round        text        NOT NULL,
    kickoff      timestamptz NOT NULL,
    home_team_id integer     NOT NULL REFERENCES teams,
    away_team_id integer     NOT NULL REFERENCES teams,
    status       text        NOT NULL            -- provider status: FT, AET, PEN, NS, PST, ...
);
CREATE INDEX IF NOT EXISTS fixtures_league_season ON fixtures (league_id, season);

-- A finished match's result: goals after extra time, never including a shoot-out.
CREATE TABLE IF NOT EXISTS fixture_results (
    fixture_id  integer PRIMARY KEY REFERENCES fixtures,
    home_goals  integer NOT NULL,
    away_goals  integer NOT NULL,
    extra_time  boolean NOT NULL
);

-- Present only when the tie went to penalties (the rating counts it as a draw).
CREATE TABLE IF NOT EXISTS shootouts (
    fixture_id      integer PRIMARY KEY REFERENCES fixture_results,
    home_penalties  integer NOT NULL,
    away_penalties  integer NOT NULL
);

CREATE TABLE IF NOT EXISTS players (
    player_id   integer PRIMARY KEY,
    name        text    NOT NULL
);

-- Every player in a matchday squad: starters, substitutes who came on, unused substitutes.
CREATE TABLE IF NOT EXISTS appearances (
    fixture_id  integer NOT NULL REFERENCES fixtures,
    team_id     integer NOT NULL REFERENCES teams,
    player_id   integer NOT NULL REFERENCES players,
    position    text    NOT NULL,                -- G, D, M, F as the provider lists it ('' if missing)
    started     boolean NOT NULL,
    minutes     integer NOT NULL,                -- 0 for an unused substitute
    goals       integer NOT NULL,
    assists     integer NOT NULL,
    PRIMARY KEY (fixture_id, player_id)
);
CREATE INDEX IF NOT EXISTS appearances_player ON appearances (player_id);
