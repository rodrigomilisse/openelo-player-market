
package com.openelo.market.trading;

import java.util.UUID;

import org.springframework.stereotype.Service;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.IRecordedTransaction;
import com.openelo.market.ledger.Ledger;

import jakarta.transaction.Transactional;

@Service
class Market {
	public static final Id<IAsset> CREDITS = new Id<>(new UUID(0, 0));

	public static Id<IAccount> PLATFORM_ACCOUNT_ID;

	private final Ledger ledger;

	private final MarketTransactionRepository marketTransactions;

	public long quoteMint(Id<IAsset> player_share) {
		return 100;
	}

	public long quoteRedeem(Id<IAsset> player_share) {
		return 90;
	}

	public Market(Ledger ledger, MarketTransactionRepository marketTransactions) {
		this.ledger = ledger;
		this.marketTransactions = marketTransactions;
		// TODO temp so that the field can remain static
		Market.PLATFORM_ACCOUNT_ID = ledger.openAccount(true);
	}

	@Transactional
	public void mint(Id<IAccount> userAccount, long amount, Id<IAsset> player_share) {
		long pricePerShare = quoteMint(player_share);
		Mint mint = new Mint(userAccount, amount, player_share, pricePerShare);
		Id<IRecordedTransaction> transactionId = ledger.post(mint);
		mint.setLedgerTransactionId(transactionId);
		marketTransactions.save(mint);
	}

	@Transactional
	public void redeem(Id<IAccount> userAccount, long amount, Id<IAsset> player_share) {
		long pricePerShare = quoteRedeem(player_share);
		Redeem redeem = new Redeem(userAccount, amount, player_share, pricePerShare);
		Id<IRecordedTransaction> transactionId = ledger.post(redeem);
		redeem.setLedgerTransactionId(transactionId);
		marketTransactions.save(redeem);
	}
}