package com.openelo.market.ledger;

public interface ITransaction {

	public Iterable<Posting> getPostings();
}
