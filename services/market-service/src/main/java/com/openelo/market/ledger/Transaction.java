package com.openelo.market.ledger;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import com.openelo.market.common.BaseEntity;

import jakarta.persistence.CollectionTable;
import jakarta.persistence.ElementCollection;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.Table;

@Table(name = "ledger_transactions")
@Entity // TODO "public" is a temporary helper for market to have access to ITransaction
		// type
public class Transaction extends BaseEntity<IRecordedTransaction> implements ITransaction {

	@ElementCollection(fetch = FetchType.LAZY)
	@CollectionTable(name = "postings", joinColumns = @JoinColumn(name = "transaction_id"))
	private List<Posting> postings;

	protected Transaction() {
	}

	public Transaction(ITransaction transaction) {
		// explicit copy
		postings = new ArrayList<>();
		transaction.getPostings().forEach(p -> postings.add(copy(p)));
	}

	// TODO temporary helper for market to easily construct Transactions
	public Transaction(Iterable<? extends IPosting> postings) {
		this.postings = new ArrayList<>();
		postings.forEach(p -> this.postings.add(copy(p)));
	}

	private Posting copy(IPosting posting) {
		return new Posting(posting);
	}

	@Override
	public Iterable<? extends IPosting> getPostings() {
		return Collections.unmodifiableList(postings);
	}
}
