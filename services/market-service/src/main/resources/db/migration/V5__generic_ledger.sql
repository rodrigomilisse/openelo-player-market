-- Replace the old account/transaction hierarchy with the generic ledger (ADR-0003).
-- Local data only, so the old tables are dropped instead of migrated.

DROP TABLE IF EXISTS postings, mints, redeems, transactions, user_accounts, platform_account, accounts, users CASCADE;

-- user
CREATE TABLE users (
	id UUID PRIMARY KEY,
	created_at TIMESTAMPTZ NOT NULL,
	username VARCHAR(100) NOT NULL
);

-- ledger
CREATE TABLE accounts (
	id UUID PRIMARY KEY,
	created_at TIMESTAMPTZ NOT NULL,
	allowed_negative BOOLEAN NOT NULL
);

CREATE TABLE ledger_transactions (
	id UUID PRIMARY KEY,
	created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE postings (
	transaction_id UUID NOT NULL REFERENCES ledger_transactions(id),
	account_id UUID NOT NULL REFERENCES accounts(id),
	asset_id UUID NOT NULL,
	amount BIGINT NOT NULL
);

CREATE INDEX postings_account_asset_idx ON postings (account_id, asset_id);

-- trading
CREATE TABLE wallets (
	id UUID PRIMARY KEY,
	created_at TIMESTAMPTZ NOT NULL,
	user_id UUID REFERENCES users(id),
	account_id UUID NOT NULL UNIQUE REFERENCES accounts(id)
);

CREATE TABLE market_transactions (
	id UUID PRIMARY KEY,
	created_at TIMESTAMPTZ NOT NULL,
	ledger_transaction_id UUID NOT NULL REFERENCES ledger_transactions(id)
);

CREATE TABLE mints (
	id UUID PRIMARY KEY REFERENCES market_transactions(id),
	user_account_id UUID NOT NULL REFERENCES accounts(id)
);

CREATE TABLE redeems (
	id UUID PRIMARY KEY REFERENCES market_transactions(id),
	user_account_id UUID NOT NULL REFERENCES accounts(id)
);
