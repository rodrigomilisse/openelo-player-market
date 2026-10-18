-- A posting is now a single transfer between two accounts instead of one signed leg.
-- Local data only, so the table is dropped instead of migrated.

DROP TABLE postings;

CREATE TABLE postings (
	transaction_id UUID NOT NULL REFERENCES ledger_transactions(id),
	from_account_id UUID NOT NULL REFERENCES accounts(id),
	to_account_id UUID NOT NULL REFERENCES accounts(id),
	amount BIGINT NOT NULL,
	asset_id UUID NOT NULL -- potentially referencing asset table eventually
);
