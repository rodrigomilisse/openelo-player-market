CREATE TABLE withdrawals (
	id UUID PRIMARY KEY REFERENCES market_transactions(id)
);
