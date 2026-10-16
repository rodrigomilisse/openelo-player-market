package com.openelo.market.ledger.exception;

import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;

public class AccountNotFoundException extends NotFoundException {
	public AccountNotFoundException(Id<IAccount> id) {
		super("Account with id:" + id.value() + " not found");
	}
}
