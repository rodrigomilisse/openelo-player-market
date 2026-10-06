package com.openelo.market.ledger;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import jakarta.persistence.CollectionTable;
import jakarta.persistence.ElementCollection;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.Inheritance;
import jakarta.persistence.InheritanceType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.Table;

@Entity
@Table(name = "transactions")
@Inheritance(strategy = InheritanceType.JOINED)
public abstract class ATransaction implements ITransaction {

	@Id
	protected UUID id;

	protected Instant createdAt;

	@ElementCollection(fetch = FetchType.LAZY)
	@CollectionTable(name = "postings", joinColumns = @JoinColumn(name = "transaction_id"))
	protected List<Posting> postings;

	protected ATransaction() {

	}

	protected Posting debit(IAccount account, long amount, AssetId assetId) {
		return new Posting(account.getId(), Math.negateExact(amount), assetId);
	}

	protected Posting credit(IAccount account, long amount, AssetId assetId) {
		return new Posting(account.getId(), amount, assetId);
	}

	@Override
	public UUID getId() {
		return this.id;
	}

	@Override
	public Instant getCreatedAt() {
		return this.createdAt;
	}

	@Override
	public Iterable<Posting> getPostings() {
		return this.postings;
	}
}
