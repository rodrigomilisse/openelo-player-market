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
@Table(name = "withdrawals")
public class Withdrawal extends ATransaction<Withdrawal> {

	protected Withdrawal() {

	}

	public Withdrawal(Platform platform, Id<IAccount> userAccountId, long amount) {

		this.postings = new ArrayList<>(1);

		Posting creditsToPlatform = new Posting(userAccountId, platform.getAccountId(), amount,
				platform.getCreditsId());

		this.postings.add(creditsToPlatform);
	}

}
