package com.openelo.market.ledger.account;

import java.util.UUID;
import com.openelo.market.user.User;
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
		super(UUID.randomUUID());
		this.owner = owner;
	}

	public User getOwner() {
		return owner;
	}
}
