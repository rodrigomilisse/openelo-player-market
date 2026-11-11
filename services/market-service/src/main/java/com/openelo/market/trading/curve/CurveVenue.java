
package com.openelo.market.trading.curve;

import org.springframework.stereotype.Service;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.IRecordedTransaction;
import com.openelo.market.ledger.Ledger;
import com.openelo.market.pricing.Quote;
import com.openelo.market.pricing.Quoter;
import com.openelo.market.pricing.ShareService;
import com.openelo.market.trading.MarketTransactionRepository;
import com.openelo.market.trading.Platform;
import com.openelo.market.trading.WalletService;
import com.openelo.market.user.IUser;

import jakarta.transaction.Transactional;

@Service
class CurveVenue {
	private final Ledger ledger;

	private final MarketTransactionRepository marketTransactionRepository;

	private final WalletService walletService;

	private final Platform platform;

	private final Quoter quoter;

	private final ShareService shareService;

	public CurveVenue(Ledger ledger, MarketTransactionRepository marketTransactions, WalletService walletService,
			Platform platform, Quoter quoter, ShareService shareService) {
		this.ledger = ledger;
		this.marketTransactionRepository = marketTransactions;
		this.walletService = walletService;
		this.platform = platform;
		this.quoter = quoter;
		this.shareService = shareService;
	}

	@Transactional
	public void mint(Id<IUser> userId, long shareAmount, Id<IAsset> player_share) {
		marketTransactionRepository.lockShare(player_share.value());

		Id<IAccount> userAccount = walletService.getAccount(userId);
		Quote quote = quoter.quoteMint(player_share, shareAmount);

		Mint mint = new Mint(shareService, platform, userAccount, shareAmount, player_share, quote);
		Id<IRecordedTransaction> transactionId = ledger.post(mint);
		mint.setLedgerTransactionId(transactionId);
		marketTransactionRepository.save(mint);
	}

	@Transactional
	public void redeem(Id<IUser> userId, long shareAmount, Id<IAsset> player_share) {
		marketTransactionRepository.lockShare(player_share.value());

		Id<IAccount> userAccount = walletService.getAccount(userId);
		long proceeds = quoter.quoteRedeem(player_share, shareAmount);

		Redeem redeem = new Redeem(shareService, platform, userAccount, shareAmount, player_share, proceeds);

		Id<IRecordedTransaction> transactionId = ledger.post(redeem);
		redeem.setLedgerTransactionId(transactionId);
		marketTransactionRepository.save(redeem);
	}
}