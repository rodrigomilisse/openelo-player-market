package com.openelo.market.ledger;

import java.time.Instant;
import java.util.UUID;

import com.openelo.market.User;

import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

@Entity
@Table(name = "user_accounts")
public class UserAccount extends AAccount {

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "owner")
	private User owner;

	protected UserAccount() {

	}

	public UserAccount(User owner) {
		this.owner = owner;
		this.id = UUID.randomUUID();
		this.createdAt = Instant.now();
	}

	public User getOwner() {
		return owner;
	}
}
