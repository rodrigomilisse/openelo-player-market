package com.openelo.market.trading.banking;

import java.util.ArrayList;

import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.Posting;

import com.openelo.market.trading.ATransaction;
import com.openelo.market.trading.Platform;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "deposits")
public class Deposit extends ATransaction<Deposit> {

	protected Deposit() {

	}

	public Deposit(Platform platform, Id<IAccount> userAccountId, long amount) {

		this.postings = new ArrayList<>(2);

		// TODO
		// Posting fundsToPlatform = new Posting(userAccount,
		// platform.getAccountId(), fundsAmount, fundType);
		Posting credtisToUser = new Posting(platform.getAccountId(), userAccountId, amount,
				platform.getCreditsId());

		// this.postings.add(fundsToPlatform);
		this.postings.add(credtisToUser);
	}

}
