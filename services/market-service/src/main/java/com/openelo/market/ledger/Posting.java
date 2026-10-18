package com.openelo.market.ledger;

import java.util.UUID;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;

import jakarta.persistence.Embeddable;

@Embeddable // TODO "public" is temporary helper for market to easily get an IPosting type
public class Posting implements IPosting {

	private UUID fromAccountId;

	private UUID toAccountId;

	private long amount;

	private UUID assetId;

	protected Posting() {
	}

	public Posting(IPosting posting) {
		this.fromAccountId = posting.getFromAccountId().value();
		this.toAccountId = posting.getToAccountId().value();
		this.amount = posting.getAmount();
		this.assetId = posting.getAssetId().value();
	}

	// TODO temporary helper for market to easily construct postings
	public Posting(Id<IAccount> fromAccountId, Id<IAccount> toAccountId, long amount, Id<IAsset> assetId) {
		this.fromAccountId = fromAccountId.value();
		this.toAccountId = toAccountId.value();
		this.amount = amount;
		this.assetId = assetId.value();
	}

	@Override
	public Id<IAccount> getFromAccountId() {
		return new Id<>(fromAccountId);
	}

	@Override
	public Id<IAccount> getToAccountId() {
		return new Id<>(toAccountId);
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
