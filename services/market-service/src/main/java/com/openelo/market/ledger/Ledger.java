package com.openelo.market.ledger;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
public class Ledger {

	TranasactionRepository tranasactionRepository;

	public Ledger(TranasactionRepository tranasactionRepository) {
		this.tranasactionRepository = tranasactionRepository;
	}

	@Transactional(propagation = Propagation.MANDATORY)
	public void post(ITransaction transaction) {
		Transaction ledgerTransaction = new Transaction(transaction);
		tranasactionRepository.save(ledgerTransaction);
	}
}
