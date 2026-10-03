package com.openelo.market.ledger;

import java.time.Instant;
import java.util.UUID;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "platform_account")
public class PlatformAccount extends AAccount {

	protected PlatformAccount() {

	}

	public PlatformAccount(UUID platformUUID) {
		this.id = platformUUID;
		this.createdAt = Instant.now();
	}

}
