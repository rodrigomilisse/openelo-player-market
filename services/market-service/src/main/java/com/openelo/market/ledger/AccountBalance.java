package com.openelo.market.ledger;

import org.hibernate.annotations.Immutable;
import org.hibernate.annotations.Synchronize;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;

import jakarta.persistence.EmbeddedId;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Immutable
@Table(name = "account_balances")
@Synchronize({ "postings" })
public class AccountBalance {

	@EmbeddedId
	private AccountBalanceKey id;

	private long balance;

	protected AccountBalance() {
	}

	Id<IAsset> getAssetId() {
		return new Id<>(id.assetId());
	}

	long getBalance() {
		return balance;
	}
}
