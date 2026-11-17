# ADR-0017: ingestion-service, match data in

- **Status**: Proposed, not yet implemented. Each item is marked decided,
  proposed or open. Amends ADR-0001's service table: ingestion-service gets its
  own database.
- **Date**: 2026-11-12

## Context

OpenElo is computed only from public match results and player minutes (Spec §1,
§5). ADR-0001 gives that data its own service, an anti-corruption layer (ACL):
the boundary where an external model is translated into the domain's language,
so that a provider's quirks never leak into the rating code.

Phase 1 (`research/FINDINGS.md`) fixed what the formula reads. Per match: the
competition and its stage, the leg of a two-legged tie, the venue, the score
after extra time (a shoot-out counts as a draw), whether there was extra time,
each team's corners, and per player the team and minutes. National-team
matches feed the player ratings as a calibration signal. Cards were tested and
not adopted; shots, possession and the other tier-3 statistics are out by the
owner's rule. Phase 1 also found that the research dataset adds shoot-out kicks
into the score and labels plain match scores "aggregate" (FINDINGS.md §3.1), a
concrete case of why provider data is translated and checked, never trusted.

The product's central promise is that anyone can recompute OpenElo from the
same raw data. A provider's licence decides whether that raw data, or ratings
derived from it, may be published at all.

## Decision

### Decided

1. **Role: an anti-corruption layer.** External data is untrusted. It is stored
   as received, validated, translated into domain events, and nothing else. No
   rating logic lives here (ADR-0001).
2. **Live data comes only from a licensed API**: football-data.org or
   API-Football (Spec §5). Scraped data never enters the production path;
   historical transfer fees stay in `research/` (out of scope here).
3. **Delivery is a transactional outbox relayed to Kafka**, events are JSON
   with a `schemaVersion`, and consumers deduplicate by event id (ADR-0001
   decisions 3 to 5).

### Proposed

4. **Runtime: Java and Spring Boot, mirroring `market-service`.** The owner
   decided Java for rating-service; one stack for every service keeps the
   conventions (Flyway, JPA with `ddl-auto=validate`, `BaseEntity`, native
   enums, typed ids) in one place. ADR-0001 lists ingestion as a plain adapter
   service, so nothing argues for another runtime.

5. **One port, one adapter per provider, and a mock adapter first.** The port
   (`MatchSource`) returns provider-neutral records: fixtures, a finished
   match's facts, and corrections. Adapters exist for football-data.org and
   API-Football. The mock adapter replays a recorded fixture file (for example
   a few weeks of real matches in the provider's own format) and is the default
   until a licence is in place. A provider is a configuration choice, never a
   code branch in the domain.

6. **Its own database, `ingestion`.** An outbox needs a database in the same
   transaction as the business change. ADR-0001 lists none for ingestion; this
   amends it. Tables, all append-only, no nullable columns (ADR-0003, ADR-0006):

   | Table | One row per |
   |---|---|
   | `raw_payloads` | provider response as received: provider, endpoint, request, body, `received_at` |
   | `match_versions` | accepted version of a match's facts: match, version number, `known_at`, payload reference |
   | `quarantined_payloads` | rejected payload: payload reference, rule broken (native enum), `quarantined_at` |
   | `quarantine_releases` | quarantined payload accepted after a fix: payload reference, `released_at` |
   | `outbox_events` | event to relay: event id, topic, body, `created_at` |
   | `relayed_events` | relayed event: event id, `relayed_at` |

   Raw payloads are kept because the recomputability promise needs the data as
   it was known on a date (decision 9), and because a rule fix must be able to
   re-validate what was rejected.

7. **`match.completed`, version 1.** Only what the formula reads, plus what is
   needed to identify, order and correct a match. Optional facts are separate
   objects or lists, never nullable fields, mirroring the schema rule:

   ```json
   {
     "schemaVersion": 1,
     "eventId": "0193…",
     "match": { "source": "API_FOOTBALL", "sourceMatchId": "1208021" },
     "matchVersion": 1,
     "knownAt": "2026-03-14T22:41:07Z",
     "kickOff": "2026-03-14T20:00:00Z",
     "competition": { "sourceCompetitionId": "39", "season": 2025, "national": false },
     "stage": "LEAGUE",
     "venue": "HOME",
     "home": { "sourceTeamId": "40" },
     "away": { "sourceTeamId": "33" },
     "result": {
       "kind": "PLAYED",
       "homeGoals": 2, "awayGoals": 1,
       "extraTime": false,
       "shootout": false
     },
     "secondLegOf": [],
     "corners": [ { "home": 7, "away": 4 } ],
     "players": [
       { "sourcePlayerId": "306", "side": "HOME", "started": true, "minutes": 90 }
     ]
   }
   ```

   - `stage` is a native enum matching the formula's stages (`LEAGUE`,
     `CUP_EARLY`, `CUP_LATE`, `SUPER_CUP`, `CONTINENTAL_QUALIFYING`,
     `CONTINENTAL_GROUP`, `CONTINENTAL_KNOCKOUT`, `CONTINENTAL_FINAL`,
     `CLUB_WORLD_CUP`, `NATIONAL_GROUP`, `NATIONAL_KNOCKOUT`). Match importance
     was not adopted in Phase 1, but the stage is a match fact and the Spec
     keeps importance as a factor, so it travels.
   - `venue` is `HOME` or `NEUTRAL`.
   - `homeGoals` and `awayGoals` are after extra time and never include
     shoot-out kicks. `shootout: true` means the tie was decided on penalties;
     the shoot-out score is not carried because the formula counts it as a draw.
   - `secondLegOf` holds the first leg's match reference when this is a second
     leg (an empty list otherwise). The aggregate follows from the two legs and
     is not stored twice.
   - `corners` is empty when the provider has none for this match: the formula
     then uses the result alone, as it did in Phase 1 for matches without
     corner data.
   - `players` lists everyone who played, with minutes, and starters with
     `started`. Unused substitutes are not listed: zero minutes is the same as
     absence to the formula.
   - `result.kind` is `PLAYED`, `AWARDED` or `ABANDONED` (decision 9).
   - Ids are the provider's until the mapping question is settled (open point
     2).

8. **Validation rules.** A payload that breaks one is quarantined, not
   published. Every rule is a named enum value so quarantine rows say why:
   - minutes outside 0 to 150, or a starter with 0 minutes;
   - a side without exactly 11 starters;
   - a player listed twice, or for both sides;
   - more minutes on one side than 11 × match length plus 5% (substitutions
     that do not add up);
   - a substitute with more minutes than were left when he could have come on
     (more than match length minus the fewest minutes of a starter on his side);
   - negative goals, or `shootout` without a level score (single match) or a
     level aggregate (second leg);
   - extra time without a stage that allows it;
   - an unknown competition, or a team that is not in that competition's
     fixture list.

   Quarantine raises an alert (a metric that counts quarantined payloads by
   rule). After a rule or mapping fix, `quarantine_releases` re-validates the
   stored payload and publishes it as the next match version; nothing is
   re-fetched unless the provider has corrected the data.

9. **Corrections and late data are new versions of the same match.** A provider
   revision, a replayed or awarded match, or a late line-up is published as
   `match.completed` again with `matchVersion` + 1 and its own `knownAt`.
   An abandoned match is published with `result.kind: ABANDONED` and no players,
   so rating-service drops it; a replay is a new match. An awarded result
   (`AWARDED`, for example a 3-0 forfeit) is published, and rating-service
   does not rate it, since nobody played. Every fact carries the time it became
   known, so rating-service can compute "as known on day D" (ADR-0018).

10. **Schedule.** Fetch fixtures for the next 14 days once a day. After a
    match's expected end (kick-off + 2 h 15 min, or + 2 h 50 min where extra
    time is possible), poll it every 15 minutes until the provider marks it
    final, then fetch line-ups and statistics. Re-fetch every final match at
    +24 h, +72 h and +7 days to catch corrections. Volume: Phase 1's coverage
    (14 leagues, their cups, UEFA competitions) is about 6,000 club matches a
    season, at most about 200 on a weekend day, so about 4 calls per match is
    well inside API-Football's 7,500 calls a day, or football-data.org's
    30 calls a minute, if spread over the evening.

### Considered: the providers

| | football-data.org | API-Football (API-Sports) |
|---|---|---|
| Free tier | 12 competitions, 10 calls/min, delayed scores, no line-ups | 100 calls/day |
| Line-ups and minutes | "Free + Deep Data", €29/month (30 calls/min); Standard €49/month for 30 competitions | In the API's fixtures endpoints; plan details not verified (page blocked) |
| Paid tiers | €12, €29, €49, €99, €199 per month | Pro $19, Ultra $29, Mega $39 per month (via RapidAPI) for 7,500, 75,000, 150,000 calls/day |
| Bridge competitions | Champions League in the free 12; Europa and Conference League not verified | Claims worldwide coverage incl. UEFA competitions; not verified |
| Corners | "Statistics" add-on, €15/month | Fixture statistics; not verified per competition |
| Terms read | 2018 terms: attribution required ("Football data provided by the Football-Data.org API"); no redistribution clause found | Terms page blocked; the site says data for "mass media distribution may require additional licenses from the relevant rights holders" |

Sources checked on 2026-11-12: football-data.org's pricing page and its 2018
terms as indexed; API-Football's prices from its RapidAPI listing and search
results (its own pricing and terms pages refused automated reads). Other
licensed options exist at enterprise prices (Sportmonks, Stats Perform/Opta,
Sportradar) and were not priced.

## Consequences

+ Provider quirks stop at the boundary; rating-service sees one shape whatever
  the source.
+ The data as known on any date can be rebuilt from `raw_payloads` and
  `match_versions`, which the recomputability promise and the hindsight replay
  both need.
+ Corrections reuse the normal path: a new version is just another event.
+ A rejected payload is never lost, and a fix re-validates it without a
  re-fetch.
  − One more database and one more outbox relay to run.
  − Raw payloads grow without bound (about 6,000 matches a season, a few
  hundred KB each with line-ups: a few GB a season). Acceptable; can move to
  object storage later.
  − Until the identity question is settled, events carry provider ids, so the
  domain sees which provider was used.
  − Fixture handling for trading (open point 5) may add a second event type.

## Alternatives considered

- **Ingestion inside rating-service**: one service fewer, but the provider's
  model would leak into the rating code, and rating-service would need network
  access and provider credentials. ADR-0001 already rejects this.
- **No raw payload store, events only**: smaller, but "as known on date D"
  could then only be rebuilt from Kafka's retention, and a quarantined payload
  would have to be re-fetched after a fix.
- **Corrections as a separate `match.corrected` event**: makes corrections
  explicit, but every consumer then merges two streams to know a match's
  current facts. One event type with a version number is simpler and orders
  itself.
- **Scraped history to warm up the ratings**: barred by Spec §5.
- **Publishing the shoot-out score**: the formula does not read it (Phase 1
  counts a shoot-out as a draw), so it is left out until something needs it.

## Open points

1. **The licence and the recomputability promise (major).** OpenElo promises
   that anyone can recompute it from the same raw data. That needs either the
   right to publish the raw match facts (results, minutes, corners) the
   ratings were computed from, or a public source of the same facts anyone can
   obtain. Neither provider's terms, as far as they could be read, grants a
   right to redistribute; football-data.org requires attribution, and
   API-Football warns that mass distribution may need licences from the rights
   holders. In some leagues the fixture data itself is claimed as a protected
   database (Football DataCo asserts EU database right over English and
   Scottish fixtures). Publishing ratings derived from the data is probably a
   separate, weaker question, but a rating nobody can check against its inputs
   does not keep the promise. Options:
   - (a) Ask both providers in writing for a licence to publish the per-match
     facts OpenElo consumes, or the derived ratings with the facts, and choose
     the provider on the answer. **Recommended first step**: cheap, and it
     decides everything else.
   - (b) Publish only the ratings and the formula, and point to the provider
     for inputs: users with their own subscription can recompute. Weakens the
     promise to "anyone who buys the same data".
   - (c) Build the input set from facts anyone may publish (official league
     and federation results pages, an open dataset), with a licensed API only
     as a timeliness check. Heavier, and coverage of minutes is the hard part.
   - (d) An enterprise licence that explicitly includes redistribution
     (Sportmonks, Stats Perform, Sportradar). Costly.
2. **Who holds the mapping from provider ids to catalog ids.** ADR-0001 gives
   the catalog (players, teams, competitions) to rating-service. Options:
   (a) rating-service owns the mapping table and resolves provider ids on
   consumption, quarantining unknowns; (b) ingestion owns the mapping and
   publishes catalog ids, which needs catalog events from rating-service and
   makes the two services depend on each other; (c) a catalog service of its
   own. **Recommendation: (a)**, because the catalog has one owner and
   ingestion stays free of domain state; the cost is that events carry
   provider ids (decision 7).
3. **Production backfill.** Phase 1 started cold in 2012 with every team at
   1500 and needed about two seasons of burn-in before predictions settled;
   player ratings need longer. Scraped history is barred. Options: (a) the
   licensed provider's history, if its licence and depth allow (football-data.org's
   "ML Pack" advertises 10 seasons; API-Football's depth for line-ups was not
   verified); (b) a stated seed date with every team at one seed rating, and
   a published burn-in period of at least two seasons before any dividend
   settles; (c) both: backfill what the licence allows, then the burn-in rule
   for the rest. **Recommendation: (c)**, with the burn-in rule written into
   the constants version so it is public.
4. **Which provider.** Follows open point 1. On price and coverage alone,
   API-Football's Pro plan covers line-ups and the bridge competitions at the
   lowest cost; football-data.org's line-ups cost €29/month for 12
   competitions, too few for the shared scale (Phase 1 used 14 leagues plus
   all UEFA rounds).
5. **Does ingestion publish fixtures?** The brief states the owner's principle
   that minting and redeeming a player's shares is suspended while his match is
   in play, which needs kick-off times in `market-service` before the match. No
   ADR settles how `market-service` learns them, and **ADR-0010 decision 12 and
   Spec §3 say the opposite: "trading does not pause during matches"**, on the
   ground that the curve's price depends on supply, not news. The two
   statements need reconciling before this is designed. If suspension is
   adopted, the natural shape is a `fixture.scheduled` event from ingestion
   (kick-off time, teams, catalog-mapped by rating-service) that
   `market-service` consumes. Not designed here.
6. **Extra time and minutes beyond 120.** Phase 1 treats a match as 90
   minutes, or 120 when anyone played past 100. If a provider reports
   stoppage time inside minutes (95, 124), the share of a match is capped at
   1; whether to carry match length explicitly in the event is open.
