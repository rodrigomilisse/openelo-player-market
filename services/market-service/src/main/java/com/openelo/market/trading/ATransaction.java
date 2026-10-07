package com.openelo.market.trading;

import com.openelo.market.common.BaseEntity;
import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IPosting;
import com.openelo.market.ledger.IRecordedTransaction;
import com.openelo.market.ledger.ITransaction;
import com.openelo.market.ledger.Posting;

import java.util.List;
import java.util.UUID;
import jakarta.persistence.Entity;
import jakarta.persistence.Inheritance;
import jakarta.persistence.InheritanceType;
import jakarta.persistence.Table;
import jakarta.persistence.Transient;

@Entity
@Table(name = "market_transactions")
@Inheritance(strategy = InheritanceType.JOINED)
public abstract class ATransaction<T> extends BaseEntity<T> implements ITransaction {

	// @ElementCollection(fetch = FetchType.LAZY)
	// @CollectionTable(name = "postings", joinColumns = @JoinColumn(name =
	// "transaction_id"))

	@Transient
	protected List<IPosting> postings;

	UUID ledgerTransactionId;

	protected ATransaction() {

	}

	protected Posting debit(/* TODO temporary name resolution */Id<com.openelo.market.ledger.IAccount> accountId,
			long amount, Id<IAsset> assetId) {
		return new Posting(accountId, Math.negateExact(amount), assetId);
	}

	protected Posting credit(/* TODO temporary name resolution */Id<com.openelo.market.ledger.IAccount> accountId,
			long amount, Id<IAsset> assetId) {
		return new Posting(accountId, amount, assetId);
	}

	@Override
	public Iterable<IPosting> getPostings() {
		return postings;
	}

	public void setLedgerTransactionId(Id<IRecordedTransaction> recordedtransactionId) {
		this.ledgerTransactionId = recordedtransactionId.value();
	}

}
