package com.openelo.market.trading.banking;

import org.springframework.stereotype.Service;

import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.IRecordedTransaction;
import com.openelo.market.ledger.Ledger;
import com.openelo.market.trading.MarketTransactionRepository;
import com.openelo.market.trading.Platform;
import com.openelo.market.trading.WalletService;
import com.openelo.market.user.IUser;

import jakarta.transaction.Transactional;

@Service
public class BankService {

	WalletService walletService;

	Platform platform;

	Ledger ledger;

	MarketTransactionRepository marketTransactionRepository;

	public BankService(WalletService walletService, Platform platform, Ledger ledger,
			MarketTransactionRepository marketTransactionRepository) {
		this.walletService = walletService;
		this.platform = platform;
		this.ledger = ledger;
		this.marketTransactionRepository = marketTransactionRepository;
	}

	@Transactional
	public void deposit(Id<IUser> userId, long amount) {
		Id<IAccount> accountId = walletService.getAccount(userId);

		Deposit deposit = new Deposit(platform, accountId, amount);

		Id<IRecordedTransaction> transactionId = ledger.post(deposit);
		deposit.setLedgerTransactionId(transactionId);
		marketTransactionRepository.save(deposit);
	}

	@Transactional
	public void withdraw(Id<IUser> userId, long amount) {
		Id<IAccount> accountId = walletService.getAccount(userId);

		Withdrawal withdrawal = new Withdrawal(platform, accountId, amount);

		Id<IRecordedTransaction> transactionId = ledger.post(withdrawal);
		withdrawal.setLedgerTransactionId(transactionId);
		marketTransactionRepository.save(withdrawal);
	}
}
