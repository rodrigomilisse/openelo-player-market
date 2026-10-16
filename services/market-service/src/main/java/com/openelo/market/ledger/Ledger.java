package com.openelo.market.ledger;

import java.lang.foreign.Linker.Option;
import java.util.Objects;
import java.util.Optional;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.exception.AccountNotFoundException;
import com.openelo.market.ledger.exception.TransactionNotFoundException;

@Service
@Transactional(propagation = Propagation.MANDATORY)
public class Ledger {

	TransactionRepository transactionRepository;

	AccountRepository accountRepository;

	public Ledger(TransactionRepository transactionRepository, AccountRepository accountRepository) {
		this.transactionRepository = transactionRepository;
		this.accountRepository = accountRepository;
	}

	public Id<IRecordedTransaction> post(ITransaction transaction) {
		Transaction ledgerTransaction = new Transaction(transaction);
		return transactionRepository.save(ledgerTransaction).getId();
	}

	public Id<IAccount> openAccount(boolean allowedNegative) {
		return accountRepository.save(new Account(allowedNegative)).getId();
	}

	public Id<IAccount> openAccount() {
		return openAccount(false);
	}

	@Transactional(readOnly = true)
	public IRecordedTransaction getTransaction(Id<IRecordedTransaction> id) {
		return transactionRepository.findById(id.value())
				.orElseThrow(() -> new TransactionNotFoundException(id));
	}

	@Transactional(readOnly = true)
	public IAccount getAccount(Id<IAccount> id) {
		return accountRepository.findById(id.value())
				.orElseThrow(() -> new AccountNotFoundException(id));
	}

	@Transactional(readOnly = true)
	public Long getBalance(Id<IAccount> accountId, Id<IAsset> assetId) {
		if (!accountRepository.existsById(accountId.value())) {
			throw new AccountNotFoundException(accountId);
		}
		return transactionRepository.getBalance(accountId.value(), assetId.value());
	}
}
