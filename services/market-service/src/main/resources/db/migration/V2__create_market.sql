DROP TABLE Account;

CREATE TABLE users (
	id UUID PRIMARY KEY,
	username VARCHAR(100) NOT NULL,
	created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE accounts (
	id UUID PRIMARY KEY,
	created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE user_accounts (
	id UUID PRIMARY KEY REFERENCES accounts(id) NOT NULL,
	owner UUID REFERENCES users(id) NOT NULL
);

CREATE TABLE platform_account (
	id UUID PRIMARY KEY REFERENCES accounts(id) NOT NULL
);

CREATE TABLE transactions (
	id UUID PRIMARY KEY,
	created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE mints (
	id UUID PRIMARY KEY REFERENCES transactions(id),
	user_account UUID REFERENCES user_accounts(id)
);

CREATE TABLE redeems (
	id UUID PRIMARY KEY REFERENCES transactions(id),
	user_account UUID REFERENCES user_accounts(id)
);


CREATE TABLE postings (
	transaction_id UUID REFERENCES transactions(id) NOT NULL,
	account_id UUID REFERENCES accounts(id) NOT NULL,
	amount BIGINT NOT NULL,
	asset UUID NOT NULL,
	created_at TIMESTAMPTZ NOT NULL
);

