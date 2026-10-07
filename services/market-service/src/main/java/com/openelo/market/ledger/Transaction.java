package com.openelo.market.ledger;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import com.openelo.market.BaseEntity;

import jakarta.persistence.CollectionTable;
import jakarta.persistence.ElementCollection;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;

@Entity
public class Transaction extends BaseEntity {

	@ElementCollection(fetch = FetchType.LAZY)
	@CollectionTable(name = "postings", joinColumns = @JoinColumn(name = "transaction_id"))
	private List<Posting> postings;

	protected Transaction() {
	}

	public Transaction(ITransaction transaction) {
		super(UUID.randomUUID());
		// explicit copy
		postings = new ArrayList<>();
		transaction.getPostings().forEach(postings::add);
	}

	private Posting copy(Posting posting) {
		return new Posting(posting.getAccount(), posting.getAmount(), posting.getAssetId());
	}

}
