package com.openelo.market.ledger;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
public class Ledger {

	@Autowired
	TranasactionRepository txs;

	public Ledger(TranasactionRepository txs) {
		this.txs = txs;
	}

	@Transactional(propagation = Propagation.MANDATORY)
	public void post(ATransaction transaction) {
		txs.save(transaction);
	}
}
