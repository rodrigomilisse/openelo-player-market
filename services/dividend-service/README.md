# dividend-service

Computes per-period dividend payout plans from collected fees and a referenced Elo snapshot. Does not touch balances: it emits `dividend.payout.requested`, and market-service applies it idempotently.
