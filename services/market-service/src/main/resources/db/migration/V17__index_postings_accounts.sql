CREATE INDEX postings_to_account_asset_idx ON postings (to_account_id, asset_id);

CREATE INDEX postings_from_account_asset_idx ON postings (from_account_id, asset_id);
