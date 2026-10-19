CREATE TABLE deposits (
	id UUID PRIMARY KEY REFERENCES market_transactions(id)
);
