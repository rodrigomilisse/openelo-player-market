package com.openelo.market.ledger.exception;

import com.openelo.market.common.Id;
import com.openelo.market.ledger.IRecordedTransaction;

public class TransactionNotFoundException extends NotFoundException {

	public TransactionNotFoundException(Id<IRecordedTransaction> id) {
		super("Transaction with id:" + id.value() + " not found");
	}
}
