package com.openelo.market.ledger;

import java.util.Optional;
import java.util.UUID;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.HttpServerErrorException.NotImplemented;

import com.openelo.market.common.Id;

@Service
public class Ledger {

	TranasactionRepository tranasactionRepository;

	AccountService accountService;

	public Ledger(TranasactionRepository tranasactionRepository, AccountService accountService) {
		this.tranasactionRepository = tranasactionRepository;
		this.accountService = accountService;
	}

	@Transactional(propagation = Propagation.MANDATORY)
	public Id<IRecordedTransaction> post(ITransaction transaction) {
		Transaction ledgerTransaction = new Transaction(transaction);
		// TODO it only make sense to give RecordedTransaction as Id type to keep
		// ITransaction as pure interface without persistance?, see below
		return tranasactionRepository.save(ledgerTransaction).getId();
	}

	/* @Transactional? Propagation? */
	public Id<IAccount> openAccount(boolean allowedNegative) {
		return accountService.openAccount(allowedNegative);
	}

	/* @Transactional? Propagation? */
	public Id<IAccount> openAccount() {
		return openAccount(false);
	}

	@Transactional(readOnly = true /* , TODO propagation = Propagation.MANDATORY? */)
	public Optional<IRecordedTransaction> find(Id<ITransaction /*
																 * ITx?? but ITx isnt supposed to have an Id so Id<ITx>
																 * is weird?
																 * LL
																 */> id) {
		throw new RuntimeException();
		// TODO implement
	}
	// TODO find balance
}
