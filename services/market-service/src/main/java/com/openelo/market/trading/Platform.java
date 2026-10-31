package com.openelo.market.trading;

import java.util.UUID;

import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.Ledger;

@Component
public class Platform {

	private static final Id<IAsset> CREDITS = new Id<>(new UUID(0, 0));

	private final Id<IAccount> accountId;

	Platform(Ledger ledger, TransactionTemplate transactionTemplate) {
		// TODO temp, in the future platform account creation is an admin/configuration
		// responsibility outside the markert
		// no proxy exists yet during construction, so @Transactional can't be used here
		this.accountId = transactionTemplate.execute(status -> ledger.openAccount());
	}

	public Id<IAsset> getCreditsId() {
		return CREDITS;
	}

	public Id<IAccount> getAccountId() {
		return accountId;
	}
}
