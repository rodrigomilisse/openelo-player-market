package com.openelo.market.trading;

import java.util.ArrayList;

import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.Posting;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "deposits")
public class Deposit extends ATransaction<Deposit> {

	protected Deposit() {

	}

	public Deposit(Id<IAccount> userAccountId, long amount) {

		this.postings = new ArrayList<>(2);

		// TODO
		// Posting fundsToPlatform = new Posting(userAccount,
		// Market.PLATFORM_ACCOUNT_ID, fundsAmount, fundType);
		Posting credtisToUser = new Posting(Market.PLATFORM_ACCOUNT_ID, userAccountId, amount,
				Market.CREDITS);

		// this.postings.add(fundsToPlatform);
		this.postings.add(credtisToUser);
	}

}
