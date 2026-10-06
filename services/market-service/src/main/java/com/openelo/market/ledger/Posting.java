package com.openelo.market.ledger;

import java.util.UUID;
import jakarta.persistence.Embeddable;

@Embeddable
public class Posting {

	private UUID accountId;

	private long amount;

	private AssetId assetId;

	protected Posting() {
	}

	public Posting(UUID account, long amount, AssetId assetId) {
		this.accountId = account;
		this.amount = amount;
		this.assetId = assetId;
	}

	public UUID getAccount() {
		return this.accountId;
	}

	public long getAmount() {
		return this.amount;
	}

	public AssetId getAssetId() {
		return this.assetId;
	}
}
