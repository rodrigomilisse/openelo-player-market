
package com.openelo.market.trading;

import java.util.UUID;

import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.IRecordedTransaction;
import com.openelo.market.ledger.Ledger;
import com.openelo.market.pricing.Quoter;
import com.openelo.market.pricing.ShareService;
import com.openelo.market.user.IUser;

import jakarta.transaction.Transactional;

@Service
class Market {
	public static final Id<IAsset> CREDITS = new Id<>(new UUID(0, 0));

	public static Id<IAccount> PLATFORM_ACCOUNT_ID;

	private final Ledger ledger;

	private final MarketTransactionRepository marketTransactionRepository;

	private final WalletRepository walletRepository;

	private final Quoter quoter;

	private final ShareService shareService;

	public Market(Ledger ledger, MarketTransactionRepository marketTransactions, WalletRepository walletRepository,
			Quoter quoter, ShareService shareService, TransactionTemplate transactionTemplate) {
		this.ledger = ledger;
		this.marketTransactionRepository = marketTransactions;
		this.walletRepository = walletRepository;
		this.quoter = quoter;
		this.shareService = shareService;
		// TODO temp, in the future platform account creation is an admin/configuration
		// responsibility outside the markert
		// no proxy exists yet during construction, so @Transactional can't be used here
		Market.PLATFORM_ACCOUNT_ID = transactionTemplate.execute(status -> ledger.openAccount());
	}

	private Id<IAccount> getAccount(Id<IUser> userId) {
		return walletRepository.findByUserId(userId.value()).orElseThrow().getAccountId();
	}

	@Transactional
	public void mint(Id<IUser> userId, long shareAmount, Id<IAsset> player_share) {

		Id<IAccount> userAccount = getAccount(userId);
		long cost = quoter.quoteMint(player_share, shareAmount);

		Mint mint = new Mint(shareService, userAccount, shareAmount, player_share, cost);
		Id<IRecordedTransaction> transactionId = ledger.post(mint);
		mint.setLedgerTransactionId(transactionId);
		marketTransactionRepository.save(mint);
	}

	@Transactional
	public void redeem(Id<IUser> userId, long shareAmount, Id<IAsset> player_share) {

		Id<IAccount> userAccount = getAccount(userId);
		long proceeds = quoter.quoteRedeem(player_share, shareAmount);

		Redeem redeem = new Redeem(shareService, userAccount, shareAmount, player_share, proceeds);

		Id<IRecordedTransaction> transactionId = ledger.post(redeem);
		redeem.setLedgerTransactionId(transactionId);
		marketTransactionRepository.save(redeem);
	}
}