# ADR-0009: Bonding curve: one pool account per player, supply as its balance

- **Status**: Accepted, not yet implemented. Amends ADR-0003 §1 (adds a
  `pricing` module). Order pricing is proposed, not decided.
- **Date**: 2026-10-19

## Context

Spec §3 prices player shares with a public, fixed bonding curve. Price is a
function of the shares outstanding, and each player's starting point is
calibrated once and never changed. The curve is permanently two-sided: users
can always mint and redeem, and redeem pays k × the mint price at the current
supply (for example k = 0.99). The curve's funding must stay separate from the
fee-funded dividend pool.

Today `Market` quotes fixed prices (100 to mint, 90 to redeem), and `Mint` and
`Redeem` post between the user's wallet account and a single platform account.
A new platform account is opened at every startup and its id is kept in memory
(ADR-0003 §3). The credits amount is `quantity × pricePerShare`.

A curve needs each player share's current supply. It could be a stored
counter, a count of mints minus redeems, or something the ledger already
records. ADR-0006 rules out storing values that can be derived, and ADR-0003
keeps players and curves out of the ledger.

## Decision

1. **Supply is a balance.** A player's shares are issued from that player's
   pool account: a mint posts them from the pool to the user, and a redeem
   posts them back. Every posting leaves one account and enters another
   (ADR-0007), so the pool's balance in the share asset is always minus the
   sum of all holdings:

   ```
   supply = −ledger.getBalance(pool, shareAsset)
   ```

   Supply is not stored (ADR-0006 decision 2). The ledger gets no new API and
   does not learn what supply means. Real securities work the same way:
   depositories issue from an issuer account and must reconcile "issued = sum
   of holdings" (EU CSDR art. 37, integrity of the issue). Here that equality
   holds by construction.

2. **One pool account per player.** It issues that player's shares, so its
   share balance is −supply, and it holds that player's credit reserve. Mint
   and redeem post between the user's wallet account and the pool. Each
   player's collateral is kept apart and can be checked on its own. The pool
   belongs to the platform, so ADR-0008's non-negative rule, which applies to
   users' wallet accounts, does not apply to it.

3. **The spread goes to a fee account.** A mint pays k × its cost to the pool
   and (1 − k) × its cost to a platform fee account, in the same ledger
   transaction. Collateral and revenue never share an account. The fee account
   must survive restarts, so it is recorded in the `platform_accounts` table
   planned in ADR-0003 §3, which is built as part of this work.

   ```
   Mint n shares
     user → pool   credits   k × cost
     user → fees   credits   (1 − k) × cost
     pool → user   share     n

   Redeem n shares
     user → pool   share     n
     pool → user   credits   proceeds
   ```

4. **The formula lives in a new `pricing` module.** It is plain Java with no
   Spring, JPA or database access, and depends on nothing in this service;
   `trading` depends on it. `trading` reads the supply and the player's start
   price and passes them in. ADR-0001 already names a `pricing` package; this
   adds it to the module list in ADR-0003 §1. The formula is public (Spec §3),
   so it can be tested and published on its own.

5. **No asset table in the ledger for now.** `trading` creates a player share's
   asset id when it lists the player. `postings.asset_id` keeps no foreign key,
   so the database does not reject unknown asset ids. An identity-only
   `assets` table in the ledger would close that gap later; the curve does not
   need it.

6. **Prices are whole minor units, and k stays a fixed percentage.** The
   formula gives every share's price in whole credits. The spread is always
   the same fraction (1 − k) of the amount, so it does not change with price.
   How k × an amount stays whole is open (open point 6).

## Order pricing (proposed, not decided)

An order covers many shares, and on a curve every share has its own price.
This section settles how the order's total is decided and who declares what.

Let price(i) be the mint price of the share that takes supply from i to i + 1.
Options for the total of an order of n shares at supply s:

- **One quote × quantity**: price(s) × n. Every share in the order gets the
  first share's price, and a redeem gives every share the top share's price.
  A buy-then-sell round trip then makes a profit out of the reserve. With
  price(i) = 100 + i and k = 0.99:

  | | One quote × quantity | Lump total |
  |---|---|---|
  | Mint 100 at supply 0 | 100 × 100 = 10,000 | 100 + … + 199 = 14,950 |
  | Redeem 100 at supply 100 | 0.99 × 200 × 100 = 19,800 | 0.99 × 14,950 |
  | Round trip | +9,800, taken from the reserve | −1%, the spread |

- **Average price × quantity**: the average of the prices the order walks
  through is the lump total divided by n, so this is the lump total shown per
  share. It adds a division and nothing else.
- **Lump total** (leaning): a mint costs price(s) + … + price(s + n − 1). The
  spread is applied once to that total: the pool receives k × total and the
  fee account (1 − k) × total. A redeem pays k × (price(s − n) + … +
  price(s − 1)).

With the lump total and decision 3, a pool always holds
k × (price(0) + … + price(supply − 1)), which is what redeeming every
outstanding share pays, whatever the curve's shape. That answers Spec §3's
concern about mass redemption, provided every share is issued through the
curve, the reserve pays for nothing but redemptions, the start price never
changes and every amount stays whole without rounding (open point 6).

A trade's price per share is then total ÷ quantity: exact as a fraction, but
not always a whole number (ADR-0006 open point 1).

**Who declares what.** The client declares the quantity of shares and nothing
about the price. The server computes the total from the public formula at the
supply it reads, so every amount it honours comes from the formula (Spec §3).
Open: see open points 7 and 8.

## Other proposals (not decided)

- **A `player_shares` table in `trading`**: `id`, `created_at`, `asset_id`,
  `player_id` (the rating-service id; no foreign key because it crosses
  services, ADR-0005 decision 2), `pool_account_id` and `start_price`. Every
  column is required, `asset_id`, `player_id` and `pool_account_id` are
  unique, and the row is never updated. There is no supply column. A pool is
  identified through this row and is not listed again in `platform_accounts`.
  Listing a player opens the pool account, creates the asset id and saves the
  row in one transaction, as `SignUp` does.

Safety checks, noted here but not planned:

- **A per-player lock.** A mint or redeem locks the player's `player_shares`
  row before reading supply, so two trades cannot both be priced at the same
  supply. Same pattern as the wallets lock proposed in ADR-0008.
- **Reconciliation.** A periodic check that each pool's credits cover the
  full-redemption value of its supply; later a job for `audit-service`.

## Consequences

+ No supply value can drift from the postings. Supply and reserve are ordinary
  balances, so a later balance cache (ADR-0006 decision 4) speeds them up
  without supply-specific code.
+ The ledger is unchanged and still knows nothing about players or curves.
+ Each player's collateral is separate and can be checked alone.
+ Fee revenue sits in its own account, ready to fund the dividend pool.
+ The formula can be tested without Spring or a database.
  − Every mint and redeem runs a balance query to read supply, until balances
  are cached.
  − One more ledger account per player.
  − Supply stays correct only while a pool is used for nothing but its
  player's mints, redeems and reserve. Shares handed out any other way (for
  example in a promotion) raise supply without funding the reserve.
  − Fees cannot be posted until `platform_accounts` exists.
  − The database does not reject unknown asset ids (decision 5).
  − `Market`, `Mint` and `Redeem` change: postings go to the pool instead of
  the platform account, mints gain a fee posting, and quotes come from
  `pricing`.

## Alternatives considered

- **A stored supply counter**, updated by every mint and redeem: fast to read,
  and usual on blockchains (ERC-20 `totalSupply`), where holdings cannot be
  summed cheaply. Here it stores a derived value twice (ADR-0006 decision 2).
  If speed is needed, balances are cached in the ledger instead.
- **Mints minus redeems**: trading rows store no quantities, so this queries
  postings anyway, with more joins, and misses any other movement out of the
  issuer.
- **Two accounts per player** (issuer and reserve): one meaning per account, at
  the cost of twice the accounts and links.
- **One issuer and one reserve for all players**: supply still works per asset,
  but collateral is pooled. A fault in one curve can spend another player's
  reserve, and no player can be reconciled alone.
- **The pool keeps the spread**: works without `platform_accounts`, but revenue
  sits inside collateral, and the pool's surplus over the full-redemption
  value grows with every trade.
- **The formula inside `trading`**: one package fewer, but harder to keep free
  of persistence and Spring.
- **An identity-only `assets` table in the ledger now**: the database would
  reject unknown asset ids, but credits would need a row too, so setting up
  credits and platform accounts would have to be solved first. Deferred
  (decision 5).
- **A whole-unit spread per share** (mint and redeem prices each defined as
  whole numbers): no rounding anywhere, but the spread would then change as a
  percentage of the price. Rejected in favour of a fixed k (decision 6).

## Open points

1. **Curve shape and k** are business decisions. The formula's interface does
   not depend on them.
2. **Share units**: whole shares or fractions (lot size, ADR-0006 open
   point 1). The total sums over the share asset's smallest unit.
3. **Platform accounts**: how `trading` tells the fee account from other
   platform accounts (ADR-0003's proposed `purpose` column, or another way),
   and who creates them.
4. **Listing players**: where the start price comes from (Spec §3's
   calibration) and what triggers a listing (an admin call or a rating-service
   event).
5. **Fee on curve trades**: Spec §3 charges curve trades more than P2P trades.
   Whether that charge is the spread alone or an extra fee on top is open.
6. **Keeping k × amount whole.** One way: with k = 99/100, make every share's
   price a multiple of 100 minor units, so every total, and k × every total, is
   whole.
7. **A limit from the client.** Supply can change between the quote a user
   sees and the moment the order runs. The client could send a bound (the most
   it will pay for a mint, the least it will accept for a redeem) and the
   order fails if the formula's total is outside it.
8. **Declaring credits instead of shares.** Whether a client may say "spend
   this many credits" and receive as many shares as that buys, instead of
   declaring the quantity.
