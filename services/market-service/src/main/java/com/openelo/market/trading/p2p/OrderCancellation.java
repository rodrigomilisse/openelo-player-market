package com.openelo.market.trading.p2p;

import java.util.ArrayList;
import java.util.UUID;

import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.Posting;
import com.openelo.market.trading.ATransaction;
import com.openelo.market.trading.Platform;
import com.openelo.market.trading.WalletService;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "order_cancellations")
class OrderCancellation extends ATransaction<OrderCancellation> {

	private UUID orderId;

	protected OrderCancellation() {

	}

	OrderCancellation(WalletService walletService, Platform platform, LimitOrder order, long remaining) {
		this.orderId = order.getId().value();

		Id<IAccount> account = walletService.getAccount(order.getUserId());
		Id<IAccount> escrow = walletService.getEscrowAccount(order.getUserId());
		this.postings = new ArrayList<>(1);
		Posting releaseToAccount = new Posting(escrow, account, order.lockedAmount(remaining), order.lockedAsset(platform));

		this.postings.add(releaseToAccount);
	}
}
