package com.openelo.market.ledger;

import java.time.Instant;
import java.util.UUID;

public interface IAccount {

	public UUID getId();

	public Instant getCreatedAt();
}
