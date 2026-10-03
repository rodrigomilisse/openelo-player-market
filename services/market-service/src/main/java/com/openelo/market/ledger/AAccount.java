package com.openelo.market.ledger;

import java.time.Instant;
import java.util.UUID;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Inheritance;
import jakarta.persistence.InheritanceType;
import jakarta.persistence.Table;

@Entity
@Table(name = "accounts")
@Inheritance(strategy = InheritanceType.JOINED)
public abstract class AAccount implements IAccount {

	@Id
	protected UUID id;

	protected Instant createdAt;

	protected AAccount() {

	}

	@Override
	public UUID getId() {
		return id;
	}

	@Override
	public Instant getCreatedAt() {
		return createdAt;
	}
}
