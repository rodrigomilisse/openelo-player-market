package com.openelo.market.ledger;

import java.util.UUID;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;

import jakarta.persistence.Embeddable;

@Embeddable // TODO "public" is temporary helper for market to easily get an IPosting type
public class Posting implements IPosting {

	private UUID accountId;

	private long amount;

	private UUID assetId;

	protected Posting() {
	}

	public Posting(IPosting posting) {
		this.accountId = posting.getAccountId().value();
		this.amount = posting.getAmount();
		this.assetId = posting.getAssetId().value();
	}

	// TODO temporary helper for market to easily construct postings
	public Posting(Id<IAccount> accountId, long amount, Id<IAsset> assetId) {
		this.accountId = accountId.value();
		this.amount = amount;
		this.assetId = assetId.value();
	}

	@Override
	public Id<IAccount> getAccountId() {
		return new Id<>(accountId);
	}

	@Override
	public long getAmount() {
		return amount;
	}

	@Override
	public Id<IAsset> getAssetId() {
		return new Id<>(assetId);
	}
}
