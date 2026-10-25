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
- [ ] Heat: mint price = curve × (1 + heat), heat added per share minted, halving every τ
- [ ] Virtual supply s₀ in the heat step
- [ ] Heat building up share by share within an order
- [ ] Heat derived from mint history (nothing stored)
- [ ] Mint fee (mint only, announced in advance)
- [ ] Constants (step, s₀, τ, fees) chosen from a target plus simulation

### Trading and accounts
- [x] Shares issued from their own pool account (listing opens it; account id = share id)
- [ ] Credits held by the pool too, not the shared platform account
- [ ] Link from a share to its player
- [ ] `platform_accounts` table, with a persisted fee account
- [ ] Mint posts the base price to the pool and the premium plus fee to the fee account
- [ ] Redeem pays the base curve back down, no fee
- [ ] One dividend pool for the whole market, split by Elo; platform cut 0%

### Market (leaning, not decided)
- [ ] 24/7 continuous limit order book for P2P trading
- [ ] Curve and book as separate venues
- [ ] Escrow postings for open orders
- [ ] Taker-only P2P fee, lower than minting
- [ ] Curve quotes shown as depth; anonymous book; platform never trades
