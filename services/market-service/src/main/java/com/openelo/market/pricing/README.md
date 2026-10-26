# pricing

The public market formulas. Pricing decides the price: it reads the ledger
directly and depends on no module except `ledger` and `common`. A share's pool
account is the ledger account whose id is the share's id (`ShareService`). Design: [ADR-0009](../../../../../../../../../docs/adr/0009-bonding-curve-pool-accounts.md),
[ADR-0010](../../../../../../../../../docs/adr/0010-market-mechanics-heat-priced-issuance.md).

## Checklist

### Pricing (this module)
- [x] `Quoter.mint` / `Quoter.redeem` for a share and an amount
- [x] Orders priced over the range they walk, not one price × amount
- [x] Time as an injected `Clock`
- [ ] Base curve shape chosen (linear placeholder today)
- [x] Heat: mint premium over the curve; every share minted in the window adds the same heat (linear)
- [x] Heat building up share by share within an order
- [x] Heat derived from mint history (nothing stored)
- [x] Integer arithmetic only; the order's premium in closed form, exact because prices are multiples of the price unit
- [ ] Cooling form chosen: hard window today, linear ramp as the smoother alternative
- [x] Mint fee (mint only): 10% of the base curve cost as a placeholder
- [ ] Constants (window, heat per share, fees) chosen from a target plus simulation

### Trading and accounts
- [x] Shares issued from their own pool account (listing opens it; account id = share id)
- [x] The credits that back redeems are held by the pool
- [ ] Link from a share to its player
- [ ] `platform_accounts` table, with a persisted fee account
- [x] Mint posts the base price to the pool and the surcharge plus fee to the platform account (a persisted fee account is still to come)
- [x] Redeem pays the base curve back down from the pool, no fee
- [ ] One dividend pool for the whole market, split by Elo; platform cut 0%

### Market (leaning, not decided)
- [ ] 24/7 continuous limit order book for P2P trading
- [ ] Curve and book as separate venues
- [ ] Escrow postings for open orders
- [ ] Taker-only P2P fee, lower than minting
- [ ] Curve quotes shown as depth; anonymous book; platform never trades

## Notes (proposed, not built)

- **Bound the history read.** Only mints newer than X contribute heat (older ones count as 0), or only the last Y mints count. A thin market can use the Y-mints rule so old purchases still matter a little; a busy one can use the time rule, since its recent mints carry nearly all the heat. The same rule lets the query load only recent transactions.

## To revisit

- **Sharing the supply between quote components.** Today `ShareService.getSupply` remembers the value per transaction so that every component of a quote reads it once. Not sure this is the best way.
- **The heat calculation.** Not convinced the current approach is the best one. Known open questions: the cooling form (hard window or linear ramp), the closed form being tied to the placeholder curve, and the constants (window, heat per share).
