package com.openelo.market.trading.p2p;

import java.util.Optional;

import org.springframework.stereotype.Service;

import com.openelo.market.common.IAsset;
import com.openelo.market.common.Id;
import com.openelo.market.ledger.IRecordedTransaction;
import com.openelo.market.ledger.Ledger;
import com.openelo.market.pricing.Quoter;
import com.openelo.market.trading.ATransaction;
import com.openelo.market.trading.MarketTransactionRepository;
import com.openelo.market.trading.Platform;
import com.openelo.market.trading.WalletService;
import com.openelo.market.user.IUser;

import jakarta.transaction.Transactional;

@Service
class P2pVenue {

	private final Ledger ledger;

	private final MarketTransactionRepository marketTransactionRepository;

	private final WalletService walletService;

	private final Platform platform;

	private final LimitOrderRepository limitOrderRepository;

	private final OpenOrderRepository openOrderRepository;

	private final OrderBook orderBook;

	private final Quoter quoter;

	P2pVenue(Ledger ledger, MarketTransactionRepository marketTransactionRepository, WalletService walletService,
			Platform platform, LimitOrderRepository limitOrderRepository, OpenOrderRepository openOrderRepository,
			OrderBook orderBook, Quoter quoter) {
		this.ledger = ledger;
		this.marketTransactionRepository = marketTransactionRepository;
		this.walletService = walletService;
		this.platform = platform;
		this.limitOrderRepository = limitOrderRepository;
		this.openOrderRepository = openOrderRepository;
		this.orderBook = orderBook;
		this.quoter = quoter;
	}

	@Transactional
	public Id<LimitOrder> place(Id<IUser> userId, Id<IAsset> share, Side side, long shareAmount, long limitPrice) {
		requirePositive(shareAmount);
		requireOnTick(limitPrice);
		marketTransactionRepository.lockShare(share.value());

		LimitOrder order = limitOrderRepository.save(new LimitOrder(userId, share, side, shareAmount, limitPrice));
		long remaining = match(order);
		if (remaining > 0) {
			record(new EscrowHold(walletService, platform, order, remaining));
		}
		return order.getId();
	}

	@Transactional
	public void cancel(Id<IUser> userId, Id<LimitOrder> orderId) {
		LimitOrder order = limitOrderRepository.findById(orderId.value()).orElseThrow();
		requireOwner(order, userId);
		marketTransactionRepository.lockShare(order.getShareId().value());

		OpenOrder open = openOrderRepository.findById(orderId.value()).orElseThrow();
		record(new OrderCancellation(walletService, platform, order, open.getRemaining()));
	}

	private long match(LimitOrder taker) {
		long remaining = taker.getQuantity();
		Optional<Long> level = orderBook.findFirstLevel(taker);
		while (level.isPresent()) {
			remaining = matchLevel(taker, level.get(), remaining);
			if (remaining == 0) {
				break;
			}
			level = orderBook.findNextLevel(taker, level.get());
		}
		return remaining;
	}

	private long matchLevel(LimitOrder taker, long price, long shareAmount) {
		long remaining = shareAmount;
		for (OpenOrder resting : orderBook.findOpenAt(taker, price, shareAmount)) {
			LimitOrder maker = resting.getOrder();
			long traded = Math.min(remaining, resting.getRemaining());
			long fee = quoter.quoteTradeFee(maker.getLimitPrice(), traded);
			record(new Trade(walletService, platform, taker, maker, traded, fee));
			remaining = Math.subtractExact(remaining, traded);
			if (remaining == 0) {
				break;
			}
		}
		return remaining;
	}

	private void record(ATransaction<?> transaction) {
		Id<IRecordedTransaction> transactionId = ledger.post(transaction);
		transaction.setLedgerTransactionId(transactionId);
		marketTransactionRepository.save(transaction);
	}

	private void requirePositive(long shareAmount) {
		if (shareAmount <= 0) {
			throw new IllegalArgumentException("Share amount must be positive, was " + shareAmount);
		}
	}

	private void requireOnTick(long limitPrice) {
		long tick = quoter.getTick();
		if (limitPrice <= 0 || !isMultipleOf(limitPrice, tick)) {
			throw new IllegalArgumentException(
					"Limit price must be a positive multiple of " + tick + ", was " + limitPrice);
		}
	}

	private static boolean isMultipleOf(long value, long step) {
		return Math.floorMod(value, step) == 0;
	}

	private void requireOwner(LimitOrder order, Id<IUser> userId) {
		if (!order.getUserId().equals(userId)) {
			throw new IllegalArgumentException("Order " + order.getId().value() + " belongs to another user");
		}
	}
}
