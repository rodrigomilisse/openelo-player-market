# Brief: finishing the Redis balance projection

Where the Redis work stands, and how to build the rest of it yourself. Read it
top to bottom once, then use §4 as your checklist.

The design lives in three ADRs. This brief doesn't repeat them; it points at
the decision you need for each step:

- **ADR-0014**: the balance projection in Redis.
- **ADR-0015**: account rollover. Only §6 here touches it.
- **ADR-0016**: the read API and the read-side boundary.

---

## 1. Summary: what's done

**The read side is built and works.** `GET users/{userId}/balances` answers:

```json
{ "available": { "<assetId>": 300, "<shareId>": 4 }, "escrowed": {} }
```

How a read flows (`projection/BalanceService`):

1. It checks the Redis key `projection:ready` (`ProjectionKeys.READY`).
2. If the key is set, it reads the account's hash `balances:{accountId}` with
   `HGETALL` and turns it into a `Balances` through `BalanceHash`.
3. If the key isn't set, or Redis is unreachable, it asks the ledger, which
   reads the `account_balances` view in Postgres (V16) through the read-only
   entity `AccountBalance`.
4. `BalanceController` turns the `Balances` into the response map.

**Nothing writes to Redis yet.** There's no outbox, no projector, no Lua script
and no rebuild. `projection:ready` is never set, so **every real request is
answered by Postgres today**. Once your projector fills the hashes and your
rebuild sets the flag, reads switch to Redis with no change to the read code.

Also done, on `master`:

- **One advisory lock per share**, taken by mint, redeem, place and cancel:
  `MarketTransactionRepository.lockShare(UUID)`.
- **Indexes on postings by account and asset** (V17), so the view only reads
  the account's own postings.

| Piece | Where |
|---|---|
| Endpoint | `projection/BalanceController` |
| Redis or Postgres choice | `projection/BalanceService` |
| Redis key names | `projection/ProjectionKeys` (the flag), `projection/BalanceHash` (the hash) |
| Hash encoding (field = asset id, value = decimal balance) | `projection/BalanceHash` |
| Domain type | `ledger/Balances` (lookups only; a missing asset reads as 0) |
| Postgres source | V16 view `account_balances`, `ledger/AccountBalance`, `AccountBalanceRepository` |
| Supply and quote endpoints | empty stubs answering 501 |
| Redis server | `infra/compose.yml`, started by `./api.py up`, with `noeviction` |

---

## 2. What you're building

ADR-0014 decisions 2 and 4–9:

```
Ledger.post ──same DB transaction──▶ ledger_outbox row
                                          │
projector (scheduled) ── claims rows ─────┘
   │  loads the transaction's postings
   │  runs the Lua script: marker + HINCRBY per posting, in one step
   └─ deletes the outbox row, commits

rebuild ── refills every hash from the view, sets projection:ready
```

You need four parts: the outbox, the Lua script, the projector and the
rebuild. Build them in that order, because each one is testable on its own
before the next exists.

---

## 3. Before you start

- `git switch redis`. This branch holds the brief; your work goes here.
- **Stop `redis-playground`** if it's still running (`docker stop
  redis-playground`). It uses the same port as the compose Redis.
- `./api.py up` starts Postgres and Redis. To open a Redis client:
  `docker exec -it infra-redis-1 redis-cli`.
- **Practise lesson 2 in `redis-cli` first** (marker first then crash, increments
  first then crash, `MULTI` not deciding). §4.2 is the script that fixes all
  three.
- **The next migration number is V18.** V16 and V17 are applied to your local
  database, so they're frozen: never edit them.

---

## 4. Steps

### 4.1 The outbox (ADR-0014 decisions 2 and 4)

1. Add migration **V18**: a table `ledger_outbox` with one column,
   `transaction_id UUID PRIMARY KEY REFERENCES ledger_transactions(id)`. It
   holds no copy of the postings, only a reference (decision 4), and no
   `created_at`, because order doesn't matter (decision 6).
2. Map it in `ledger`: a small `@Entity` with an `@Id UUID transactionId`, and a
   repository for it.
3. In `Ledger.post`, after saving the transaction, save an outbox row with the
   new transaction's id. Both run in the caller's transaction (the ledger is
   `MANDATORY`), so they commit together or not at all. That's the whole point
   of an outbox.

**Check it:** make a deposit with `./api.py`, then run
`./api.py db "select * from ledger_outbox"`. One row per transaction, and none
for a request that failed.

### 4.2 The Lua script (ADR-0014 decision 7)

It receives one transaction and its postings, and it must:

1. Set the marker `projected:{transactionId}` with `SET … NX EX 86400`.
2. **Only if the marker was new**, run `HINCRBY` on every posting: minus the
   amount on the from-account's hash, plus the amount on the to-account's hash,
   with the asset id as the field.
3. Return 1 if it applied the transaction, 0 if it was already applied.

Lay out the arguments so one call carries any number of postings. For example:

- `KEYS[1]` = the marker; then, per posting, the from-account's hash key and the
  to-account's hash key.
- `ARGV[1]` = the marker's lifetime; then, per posting, the asset field and the
  amount.

The rules:

- **Build every key and field in Java with `BalanceHash`:** `key(accountId)`
  and `toField(assetId)`. Never use `Id.toString()`, which writes
  `Id[value=…]`. The reader parses with `BalanceHash` too, so the two can't
  disagree.
- **Never compute `-amount` with `tonumber`.** Lua numbers in Redis are
  floating-point and lose precision above 2^53. Join text instead,
  `'-' .. amount`, and let `HINCRBY` parse it as an exact integer.
- **Never delete a field that reaches 0.** ADR-0016 decision 1 lists assets back
  at zero, and Postgres does the same, so Redis must too.
- When `SET … NX` doesn't set the key, `redis.call` returns `false`, so
  `if redis.call('SET', …) then` works.

Put the script in `src/main/resources/redis/`, load it as a
`DefaultRedisScript<Long>`, and run it with
`redis.execute(script, keys, args...)` on the `StringRedisTemplate`.

**Check it** with `redis-cli --eval` before writing any Java (lesson 2, step 4):
run it twice with the same marker, and it should return 1 and then 0, changing
nothing the second time.

### 4.3 The projector (ADR-0014 decisions 6 and 8)

A scheduled bean in `projection` (add `@EnableScheduling` to a config). Each
tick, in **one database transaction**:

1. **Claim a batch of outbox rows** with `FOR UPDATE SKIP LOCKED`, so several
   projector instances never take the same row (decision 6). In Spring Data,
   use `@Lock(PESSIMISTIC_WRITE)` plus the lock-timeout hint `-2`, which
   Hibernate turns into `SKIP LOCKED`. Check the SQL it generates with
   `spring.jpa.show-sql=true`.
2. **For each row:** load the transaction's postings
   (`ledger.getTransaction(id).getPostings()`), run the script, then delete the
   row.
3. **Commit.**

What makes this safe: if Redis fails, the exception rolls the database
transaction back, so the rows stay and the next tick retries them. If the
process dies after the script ran but before the commit, the rows come back,
and the marker makes the retry a no-op (decision 8).

**Check it:** start the app, deposit, then run
`HGETALL balances:{accountId}` in `redis-cli`. Compare the result with
`./api.py db "select * from account_balances where account_id = '…'"`. Both
should show the same numbers, and `ledger_outbox` should be empty again.

**A decision for you:** ADR-0016 decision 6 says transactions reach
`projection` through an interface it defines, implemented by the ledger. Taken
literally, the ledger would then depend on `projection`, against "the ledger
depends on nothing". The usual way out is for the ledger to expose what's
pending (for example a public outbox repository, or `Ledger` methods to claim
and complete rows), with `projection` calling it. Choose one before writing the
projector, and record it in a new ADR.

### 4.4 The rebuild (ADR-0014 decision 9, ADR-0016 decision 10)

It refills Redis from Postgres, for the first start and after Redis loses data:

1. **Take the same advisory lock as the projector**, so they never run at the
   same time. Hash a fixed name in SQL, for example
   `pg_advisory_xact_lock(hashtextextended('projection', 0))`. Never derive
   lock keys in Java.
2. In **one `REPEATABLE READ` transaction**, so both reads see the same moment:
   - read every row of `account_balances`;
   - read the ids of the pending outbox rows.
3. Replace each account's hash with what you read: `DEL`, then `HSET` through
   `BalanceHash`.
4. Set the marker of every pending outbox row. The balances you read already
   include those transactions, so the projector must skip them.
5. **Set `projection:ready` last.** Until then, reads keep going to Postgres.

Decide when it runs (ADR-0014 open point 4): at startup when the flag is
missing, on an admin command, or both.

**Check it:** `FLUSHALL` in `redis-cli` (reads fall back to Postgres), run the
rebuild, then compare the endpoint with the view.

---

## 5. Done means

- A deposit, a mint and a trade each show up in `HGETALL` within one projector
  tick.
- `projection:ready` is set, and the endpoint answers from Redis. To see which
  path answered, put an obviously different value in one field by hand, as the
  checks in this branch did.
- Killing the app mid-run and restarting it never double-counts: the markers
  prevent it.
- Every hash matches the view.

---

## 6. Afterwards

- **A parity test.** Ask Claude to write it: a JUnit test that runs a few
  transactions, reads balances from Redis and from Postgres, and asserts they
  match. It's agreed that it starts `@Disabled`.
- **The wallet cache** (ADR-0014 decision 11, ADR-0015 decisions 8 and 15) isn't
  built. `BalanceService` still looks up account ids in Postgres. That's
  deliberate, because ADR-0015's rollover will change how the cache is updated.
  The TODO in `BalanceService` marks the spot.
- **The supply endpoint** stays a 501 until ADR-0015's pool rollover; see the
  TODO in `SupplyController`.
- **The ADR-0014 open points** still open: polling interval and batch size
  (and an after-commit nudge to cut the lag), reconciliation, and when the
  rebuild runs.

---

## 7. House rules that apply here

- **Computed reads go in a view** mapped as an `@Immutable` entity with
  `@Synchronize`, never as native SQL strings in Java. A lock is a command, not
  a computed read, so `lockShare` stays native.
- **Integers only for money.** `Math.*Exact` in Java; text and `HINCRBY` in Lua.
- **Words:** *balance* means what an account holds; *amount* means what a
  posting moves.
- **Comments only for technical traps**, never for business or design reasons
  (those belong in ADRs), and never to say what a class is.
- **A design change gets an ADR first.** New ADRs reference older ones and
  never edit them.
