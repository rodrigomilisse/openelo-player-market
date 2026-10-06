package com.openelo.market.ledger;

import java.time.Instant;
import java.util.UUID;

import jakarta.persistence.Embeddable;

@Embeddable
public class Posting {

	private UUID accountId;

	private long amount;

	private UUID asset;

	protected Posting() {
	}

	public Posting(UUID account, long amount, UUID asset) {
		this.accountId = account;
		this.amount = amount;
		this.asset = asset;
	}

	public UUID getAccount() {
		return this.accountId;
	}

	public long getAmount() {
		return this.amount;
	}

	public UUID getAsset() {
		return this.asset;
	}
}
