package com.openelo.market.trading;

import org.springframework.stereotype.Service;

import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.IRecordedTransaction;
import com.openelo.market.ledger.Ledger;
import com.openelo.market.user.IUser;

import jakarta.transaction.Transactional;

@Service
public class BankService {

	WalletRepository walletRepository;

	Ledger ledger;

	MarketTransactionRepository marketTransactionRepository;

	public BankService(WalletRepository walletRepository, Ledger ledger,
			MarketTransactionRepository marketTransactionRepository) {
		this.walletRepository = walletRepository;
		this.ledger = ledger;
		this.marketTransactionRepository = marketTransactionRepository;
	}

	@Transactional
	public void deposit(Id<IUser> userId, long amount) {
		Id<IAccount> accountId = getAccount(userId);

		Deposit deposit = new Deposit(accountId, amount);

		Id<IRecordedTransaction> transactionId = ledger.post(deposit);
		deposit.setLedgerTransactionId(transactionId);
		marketTransactionRepository.save(deposit);
	}

	@Transactional
	public void withdraw(Id<IUser> userId, long amount) {
		Id<IAccount> accountId = getAccount(userId);

		Withdrawal withdrawal = new Withdrawal(accountId, amount);

		Id<IRecordedTransaction> transactionId = ledger.post(withdrawal);
		withdrawal.setLedgerTransactionId(transactionId);
		marketTransactionRepository.save(withdrawal);
	}

	public long getBalance(Id<IUser> userId) {
		return ledger.getBalance(getAccount(userId), Market.CREDITS);
	}

	// TODO method duplicated in market
	private Id<IAccount> getAccount(Id<IUser> userId) {
		return walletRepository.findByUserId(userId.value()).orElseThrow().getAccountId();
	}
}
