-- Every trader gets an escrow account next to their wallet account: sign-up opens it for
-- new users, and existing wallets get one here.
ALTER TABLE wallets ADD COLUMN escrow_account_id UUID UNIQUE REFERENCES accounts(id);

CREATE TEMPORARY TABLE escrow_backfill ON COMMIT DROP AS
	SELECT id AS wallet_id, gen_random_uuid() AS account_id FROM wallets;
INSERT INTO accounts (id, created_at) SELECT account_id, now() FROM escrow_backfill;
UPDATE wallets w SET escrow_account_id = b.account_id FROM escrow_backfill b WHERE b.wallet_id = w.id;

ALTER TABLE wallets ALTER COLUMN escrow_account_id SET NOT NULL;

CREATE TYPE side AS ENUM ('BUY', 'SELL');

CREATE TABLE limit_orders (
	id UUID PRIMARY KEY,
	created_at TIMESTAMPTZ NOT NULL,
	user_id UUID NOT NULL REFERENCES users(id),
	share_id UUID NOT NULL,
	side side NOT NULL,
	quantity BIGINT NOT NULL,
	limit_price BIGINT NOT NULL
);

-- A trade's price is the maker's limit price and its quantity is in its postings, so
-- neither is stored (ADR-0006).
CREATE TABLE trades (
	id UUID PRIMARY KEY REFERENCES market_transactions(id),
	taker_order_id UUID NOT NULL REFERENCES limit_orders(id),
	maker_order_id UUID NOT NULL REFERENCES limit_orders(id)
);

CREATE TABLE escrow_holds (
	id UUID PRIMARY KEY REFERENCES market_transactions(id),
	order_id UUID NOT NULL UNIQUE REFERENCES limit_orders(id)
);

CREATE TABLE order_cancellations (
	id UUID PRIMARY KEY REFERENCES market_transactions(id),
	order_id UUID NOT NULL UNIQUE REFERENCES limit_orders(id)
);

-- An order is open while its trades have not moved all its shares and it is not cancelled.
CREATE VIEW open_orders AS
SELECT o.id AS order_id, CAST(o.quantity - f.filled AS BIGINT) AS remaining
FROM limit_orders o
CROSS JOIN LATERAL (
	SELECT COALESCE(SUM(p.amount), 0) AS filled
	FROM trades t
	JOIN market_transactions m ON m.id = t.id
	JOIN postings p ON p.transaction_id = m.ledger_transaction_id AND p.asset_id = o.share_id
	WHERE o.id IN (t.taker_order_id, t.maker_order_id)
) f
WHERE f.filled < o.quantity
	AND NOT EXISTS (SELECT 1 FROM order_cancellations c WHERE c.order_id = o.id);
