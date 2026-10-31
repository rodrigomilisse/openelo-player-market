-- ADR-0012/0013: the book is read through one frontier per price level, over the orders that
-- rested, with each level's queue ordered by the order's created_at, then its id.

-- target of the composite foreign key from escrow_holds
ALTER TABLE limit_orders ADD UNIQUE (id, share_id, side, limit_price, created_at);

-- Each hold carries its order's level and posting time so the book can be indexed by them;
-- the composite foreign key keeps the copies equal to the order's values.
ALTER TABLE escrow_holds
	ADD COLUMN share_id UUID,
	ADD COLUMN side side,
	ADD COLUMN limit_price BIGINT,
	ADD COLUMN order_created_at TIMESTAMPTZ;

UPDATE escrow_holds h
SET share_id = o.share_id, side = o.side, limit_price = o.limit_price, order_created_at = o.created_at
FROM limit_orders o
WHERE o.id = h.order_id;

ALTER TABLE escrow_holds
	ALTER COLUMN share_id SET NOT NULL,
	ALTER COLUMN side SET NOT NULL,
	ALTER COLUMN limit_price SET NOT NULL,
	ALTER COLUMN order_created_at SET NOT NULL,
	ADD FOREIGN KEY (order_id, share_id, side, limit_price, order_created_at)
		REFERENCES limit_orders (id, share_id, side, limit_price, created_at);

CREATE INDEX escrow_holds_book_idx ON escrow_holds (share_id, side, limit_price, order_created_at, order_id);

-- Lookups made per visited order (ADR-0013 decision 2); without these each one scans the whole
-- table, so reading the book grows with the market's history.

-- the frontier lookup, and an order's fills as a maker
CREATE INDEX trades_maker_order_idx ON trades (maker_order_id);

-- an order's fills as a taker
CREATE INDEX trades_taker_order_idx ON trades (taker_order_id);

-- a trade's share posting
CREATE INDEX postings_transaction_idx ON postings (transaction_id);

-- A level's frontier: its latest order that has been a maker. Everything before it is closed
-- (ADR-0012); '-infinity' when nothing at the level has been filled yet.
CREATE FUNCTION level_frontier(share UUID, resting_side side, price BIGINT) RETURNS TIMESTAMPTZ
LANGUAGE sql STABLE AS $$
	SELECT coalesce((
		SELECT h.order_created_at FROM escrow_holds h
		WHERE h.share_id = share AND h.side = resting_side AND h.limit_price = price
			AND EXISTS (SELECT 1 FROM trades t WHERE t.maker_order_id = h.order_id)
		ORDER BY h.order_created_at DESC
		LIMIT 1), '-infinity')
$$;
