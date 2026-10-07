package com.openelo.market.ledger;

public interface ITransaction {

	public Iterable<? extends IPosting> getPostings();
}
