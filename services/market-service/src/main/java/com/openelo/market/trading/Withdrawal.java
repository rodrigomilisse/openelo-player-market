package com.openelo.market.trading;

import java.util.ArrayList;

import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.Posting;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "withdrawals")
public class Withdrawal extends ATransaction<Withdrawal> {

	protected Withdrawal() {

	}

	public Withdrawal(Id<IAccount> userAccountId, long amount) {

		this.postings = new ArrayList<>(1);

		Posting creditsToPlatform = new Posting(userAccountId, Market.PLATFORM_ACCOUNT_ID, amount,
				Market.CREDITS);

		this.postings.add(creditsToPlatform);
	}

}
