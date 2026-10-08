package com.openelo.market.trading;

import java.util.UUID;

import com.openelo.market.common.BaseEntity;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.user.IUser;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "wallets")
class Wallet extends BaseEntity<Wallet> {

	private UUID userId;

	private UUID accountId;

	protected Wallet() {
	}

	Wallet(Id<IUser> user, Id<IAccount> account) {
		this.userId = user.value();
		this.accountId = account.value();
	}

	Id<IUser> getUserId() {
		return new Id<>(userId);
	}

	Id<IAccount> getAccountId() {
		return new Id<>(accountId);
	}
}
