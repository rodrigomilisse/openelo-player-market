package com.openelo.market.trading.p2p;

import java.time.Instant;
import java.util.ArrayList;
import java.util.UUID;

import com.openelo.market.common.Id;
import com.openelo.market.ledger.IAccount;
import com.openelo.market.ledger.Posting;
import com.openelo.market.trading.ATransaction;
import com.openelo.market.trading.Platform;
import com.openelo.market.trading.WalletService;

import jakarta.persistence.Embedded;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "escrow_holds")
class EscrowHold extends ATransaction<EscrowHold> {

	private UUID orderId;

	// the order's level and posting time, copied so the book can be indexed
	// by them; a foreign key keeps them equal to the order's (ADR-0013)
	@Embedded
	private Level level;

	private Instant orderCreatedAt;

	protected EscrowHold() {

	}

	EscrowHold(WalletService walletService, Platform platform, LimitOrder order, long shareAmount) {
		this.orderId = order.getId().value();
		this.level = order.getLevel();
		this.orderCreatedAt = order.getCreatedAt();

		Id<IAccount> account = walletService.getAccount(order.getUserId());
		Id<IAccount> escrow = walletService.getEscrowAccount(order.getUserId());
		this.postings = new ArrayList<>(1);
		Posting lockToEscrow = new Posting(account, escrow, order.lockedAmount(shareAmount), order.lockedAsset(platform));

		this.postings.add(lockToEscrow);
	}
}
