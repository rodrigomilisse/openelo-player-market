
package com.openelo.market.trading;

import java.util.UUID;

import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.IRecordedTransaction;
import com.openelo.market.ledger.Ledger;
import com.openelo.market.user.IUser;

import jakarta.transaction.Transactional;

@Service
class Market {
	public static final Id<IAsset> CREDITS = new Id<>(new UUID(0, 0));

	public static Id<IAccount> PLATFORM_ACCOUNT_ID;

	private final Ledger ledger;

	private final MarketTransactionRepository marketTransactions;

	private final WalletRepository walletRepository;

	public long quoteMint(Id<IAsset> player_share) {
		return 100;
	}

	public long quoteRedeem(Id<IAsset> player_share) {
		return 90;
	}

	public Market(Ledger ledger, MarketTransactionRepository marketTransactions, WalletRepository walletRepository,
			TransactionTemplate transactionTemplate) {
		this.ledger = ledger;
		this.marketTransactions = marketTransactions;
		this.walletRepository = walletRepository;
		// TODO temp, in the future platform account creation is an admin/configuration
		// responsibility outside the markert
		// no proxy exists yet during construction, so @Transactional can't be used here
		Market.PLATFORM_ACCOUNT_ID = transactionTemplate.execute(status -> ledger.openAccount());
	}

	private Id<IAccount> getAccount(Id<IUser> userId) {
		return walletRepository.findByUserId(userId.value()).orElseThrow().getAccountId();
	}

	@Transactional
	public void mint(Id<IUser> userId, long amount, Id<IAsset> player_share) {

		Id<IAccount> userAccount = getAccount(userId);
		long pricePerShare = quoteMint(player_share);

		Mint mint = new Mint(userAccount, amount, player_share, pricePerShare);
		Id<IRecordedTransaction> transactionId = ledger.post(mint);
		mint.setLedgerTransactionId(transactionId);
		marketTransactions.save(mint);
	}

	@Transactional
	public void redeem(Id<IUser> userId, long amount, Id<IAsset> player_share) {

		Id<IAccount> userAccount = getAccount(userId);
		long pricePerShare = quoteRedeem(player_share);

		Redeem redeem = new Redeem(userAccount, amount, player_share, pricePerShare);

		Id<IRecordedTransaction> transactionId = ledger.post(redeem);
		redeem.setLedgerTransactionId(transactionId);
		marketTransactions.save(redeem);
	}
}