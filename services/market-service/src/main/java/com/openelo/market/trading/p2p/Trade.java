package com.openelo.market.trading.p2p;

import java.util.ArrayList;
import java.util.UUID;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.Posting;
import com.openelo.market.trading.ATransaction;
import com.openelo.market.trading.Platform;
import com.openelo.market.trading.WalletService;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;

// The taker pays the fee; the maker gets exactly their limit price.
@Entity
@Table(name = "trades")
class Trade extends ATransaction<Trade> {

	private UUID takerOrderId;

	private UUID makerOrderId;

	protected Trade() {

	}

	Trade(WalletService walletService, Platform platform, LimitOrder taker, LimitOrder maker, long shareAmount, long fee) {
		this.takerOrderId = taker.getId().value();
		this.makerOrderId = maker.getId().value();

		Id<IAccount> takerAccount = walletService.getAccount(taker.getUserId());
		Id<IAccount> makerAccount = walletService.getAccount(maker.getUserId());
		Id<IAccount> makerEscrow = walletService.getEscrowAccount(maker.getUserId());
		Id<IAsset> share = maker.getShareId();
		long value = Math.multiplyExact(maker.getLimitPrice(), shareAmount);
		this.postings = new ArrayList<>(3);
		if (taker.getSide() == Side.BUY) {
			Posting paymentToSeller = new Posting(takerAccount, makerAccount, value, platform.getCreditsId());
			Posting feeToPlatform = new Posting(takerAccount, platform.getAccountId(), fee, platform.getCreditsId());
			Posting sharesToBuyer = new Posting(makerEscrow, takerAccount, shareAmount, share);

			this.postings.add(paymentToSeller);
			this.postings.add(feeToPlatform);
			this.postings.add(sharesToBuyer);
		} else {
			long proceeds = Math.subtractExact(value, fee);
			Posting proceedsToSeller = new Posting(makerEscrow, takerAccount, proceeds, platform.getCreditsId());
			Posting feeToPlatform = new Posting(makerEscrow, platform.getAccountId(), fee, platform.getCreditsId());
			Posting sharesToBuyer = new Posting(takerAccount, makerAccount, shareAmount, share);

			this.postings.add(proceedsToSeller);
			this.postings.add(feeToPlatform);
			this.postings.add(sharesToBuyer);
		}
	}
}
