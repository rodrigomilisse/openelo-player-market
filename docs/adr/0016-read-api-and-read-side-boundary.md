# ADR-0016: Read API and read-side boundary

- **Status**: Accepted in part, not yet implemented. Each item is marked
  decided or proposed. Amends ADR-0014 decisions 3, 9, 10 and 12, settles
  its open point 2, and amends ADR-0015 decision 15.
- **Date**: 2026-11-02

## Context

ADR-0014 lists one read endpoint per balance: credits, holdings, escrow and
supply. A client loads all of a user's balances when the app opens and
refreshes them now and then, rather than querying each one per screen, so
one response serves it better than three.

ADR-0014 also splits the read side between `ledger` (balances) and `trading`
(the wallet cache). The read side could later run as its own service. One
reason is to deploy copies of it in several regions, close to users, while
the money core stays in one place (ADR-0001 decision 2). Redis itself sits
next to the application, not the user; what it saves is Postgres work, not
the network path to the user.

## Decision

### Decided

1. **One endpoint returns all of a user's balances**: `GET users/{userId}/balances`,
   grouped by status into `available` (the user's account) and `escrowed`
   (held by open orders), each a map from asset id to amount, so a client
   finds a holding by asset directly. Catalogue data such as a share's player
   is the same for every user and comes from its own resource, so values stay
   bare amounts; if per-holding data is ever needed (for example an average
   buy price), values become objects, a planned breaking change. Replaces
   ADR-0014 decision 12's holdings and escrow endpoints.

   A map holds every asset the account has ever had a posting in, including
   those back at zero; an asset never transacted is absent and reads as zero.
   This settles ADR-0014 open point 2: the projector keeps a field that returns
   to zero, so Redis and Postgres answer alike.
2. **`GET bank/balance/{userId}` is removed.** `bank` keeps deposit and
   withdraw.
3. **Supply and quote are separate endpoints.** Supply says how many shares
   circulate; the quote says what minting or redeeming an amount costs now.
   Both exist as empty endpoints answering `501 Not Implemented` until pool
   rollover (ADR-0015) and the heat rework settle what they read.
4. **The read side is meant to become its own service.** It starts as a
   package in `market-service`, because a separate service needs a transport
   that does not exist yet: the outbox relayed to Kafka (ADR-0001), and
   rollover events from trading (ADR-0015).

### Proposed

5. **The read side is one package, `projection`**, holding the projector, the
   Redis reads and the read endpoints. It owns every Redis key (`balances:`,
   `wallet:`, `pool:`, `projected:`). Nothing outside it reads Redis.
6. **Transactions reach it through an interface it defines.** Today the
   ledger's outbox poller implements it; later a Kafka consumer does, and the
   package moves out by changing the transport, not its code.
7. **ADR-0015 decision 15's interface moves to `projection`.** `projection`
   defines it and trading implements it, so the ledger no longer carries a
   read-side concern.
8. **Endpoint paths**: `GET users/{userId}/balances`;
   `GET curve/shares/{shareId}/supply` as in ADR-0014;
   `GET curve/shares/{shareId}/quote` with the side and the amount as query
   parameters.
9. **The quote reads Postgres for now.** It needs heat, which scans the pool's
   postings in Postgres and is not projected. Serving supply from Redis would
   save only the cheap half. Whether heat can be projected is decided with the
   heat rework; a sliding window is not a running sum, since mints must drop
   out as they age.
10. **The readiness flag is `projection:ready`**, replacing ADR-0014's
    `balances:ready`. Inside the `balances:` namespace, a scan over account
    hashes returns the flag too, and a rebuild that clears `balances:*` deletes
    its own flag. All key names live in one place in `projection`, shared by
    the readers and the projector.

## Consequences

+ A client gets every balance in one call.
+ The read side has one owner and one boundary, ready to move out.
+ The response does not depend on how holds are stored.
  − The quote endpoint gains little until heat is projected.
  − Two ADR-0014 mechanisms only work while the read side shares a process
  with `market-service`: the Postgres fallback (decision 10) and filling the
  wallet cache from Postgres (decision 11). Once it moves out, wallet
  mappings must arrive as events (sign-up and rollover), and the fallback
  must be replaced or dropped.

## Alternatives considered

- **One endpoint per balance** (ADR-0014): more calls for a client that wants
  them all.
- **Grouping by asset** (`{ asset, available, escrowed }`): equivalent
  information, grouped on the other axis; the choice is preference.
- **Lists of `{ asset, amount }`**: entries can gain fields without breaking
  clients, but a client must search a list to find one holding.
- **A separate service now**: needs Kafka and rollover events first.
- **The split of ADR-0014** (balances in `ledger`, wallet cache in
  `trading`): no single boundary to extract.

## Open points

1. **Behaviour while Redis is down**: falling back to Postgres or failing
   reads fast. Left as a detail of ADR-0014 decision 10.
2. **Response fields beyond asset and amount**, such as share names, once a
   share is linked to its player.
