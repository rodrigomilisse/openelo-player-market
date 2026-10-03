package com.openelo.market.ledger;

import java.time.Instant;
import java.util.UUID;

public interface ITransaction {

	public UUID getId();

	public Instant getCreatedAt();

	public Iterable<Posting> getPostings();
}
