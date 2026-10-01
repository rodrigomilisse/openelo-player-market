package com.openelo.market.ledger;

import java.time.Instant;
import java.util.UUID;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;

@Entity
public class Account {

	@Id
	private UUID id;

	private String owner;

	private Instant createdAt;

	protected Account() {

	}

	public Account(String owner) {
		this.id = UUID.randomUUID();
		this.owner = owner;
		this.createdAt = Instant.now();
	}

	public Instant getCreatedAt() {
		return createdAt;
	}

	public UUID getId() {
		return id;
	}

	public String getOwner() {
		return owner;
	}
}
