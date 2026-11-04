-- One definition of a balance: each posting is an inflow for its to-account and an outflow
-- for its from-account. Postgres pushes a filter on account or asset into both halves, so
-- reading one account never sums the others.
CREATE VIEW account_balances AS
SELECT account_id, asset_id, CAST(SUM(amount) AS BIGINT) AS balance
FROM (
	SELECT to_account_id AS account_id, asset_id, amount FROM postings
	UNION ALL
	SELECT from_account_id, asset_id, -amount FROM postings
) entries
GROUP BY account_id, asset_id;
